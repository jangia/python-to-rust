use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use regex::Regex;
use std::fs;
use std::sync::LazyLock;

static TIMESTAMP_PATTERNS: LazyLock<Vec<(Regex, &'static str)>> = LazyLock::new(|| {
    vec![
        (
            Regex::new(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z").unwrap(),
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ),
        (
            Regex::new(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z").unwrap(),
            "%Y-%m-%dT%H:%M:%SZ",
        ),
        (
            Regex::new(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}").unwrap(),
            "%Y-%m-%d %H:%M:%S",
        ),
        (
            Regex::new(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}").unwrap(),
            "%Y/%m/%d %H:%M:%S",
        ),
    ]
});

static LEVEL_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[?(INFO|ERROR|WARN|DEBUG|TRACE|FATAL)\]?").unwrap());

struct TimestampResult {
    year: i32,
    month: u8,
    day: u8,
    hour: u8,
    minute: u8,
    second: u8,
    microsecond: u32,
}

fn parse_timestamp(line: &str) -> (Option<TimestampResult>, String) {
    for (pattern, fmt) in TIMESTAMP_PATTERNS.iter() {
        if let Some(m) = pattern.find(line) {
            let matched = m.as_str();
            let remaining = format!("{}{}", &line[..m.start()], &line[m.end()..]);
            let (year, month, day, hour, minute, second, microsecond) =
                parse_datetime(matched, fmt);
            return (
                Some(TimestampResult {
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    second,
                    microsecond,
                }),
                remaining,
            );
        }
    }
    (None, line.to_string())
}

fn parse_datetime(s: &str, fmt: &str) -> (i32, u8, u8, u8, u8, u8, u32) {
    match fmt {
        "%Y-%m-%dT%H:%M:%S.%fZ" => {
            let year: i32 = s[0..4].parse().unwrap();
            let month: u8 = s[5..7].parse().unwrap();
            let day: u8 = s[8..10].parse().unwrap();
            let hour: u8 = s[11..13].parse().unwrap();
            let minute: u8 = s[14..16].parse().unwrap();
            let second: u8 = s[17..19].parse().unwrap();
            let frac_str = &s[20..s.len() - 1];
            let microsecond = parse_fractional_to_microseconds(frac_str);
            (year, month, day, hour, minute, second, microsecond)
        }
        "%Y-%m-%dT%H:%M:%SZ" => {
            let year: i32 = s[0..4].parse().unwrap();
            let month: u8 = s[5..7].parse().unwrap();
            let day: u8 = s[8..10].parse().unwrap();
            let hour: u8 = s[11..13].parse().unwrap();
            let minute: u8 = s[14..16].parse().unwrap();
            let second: u8 = s[17..19].parse().unwrap();
            (year, month, day, hour, minute, second, 0)
        }
        "%Y-%m-%d %H:%M:%S" | "%Y/%m/%d %H:%M:%S" => {
            let year: i32 = s[0..4].parse().unwrap();
            let month: u8 = s[5..7].parse().unwrap();
            let day: u8 = s[8..10].parse().unwrap();
            let hour: u8 = s[11..13].parse().unwrap();
            let minute: u8 = s[14..16].parse().unwrap();
            let second: u8 = s[17..19].parse().unwrap();
            (year, month, day, hour, minute, second, 0)
        }
        _ => panic!("Unknown format: {}", fmt),
    }
}

fn parse_fractional_to_microseconds(frac: &str) -> u32 {
    let mut padded = frac.to_string();
    while padded.len() < 6 {
        padded.push('0');
    }
    padded.truncate(6);
    padded.parse().unwrap_or(0)
}

fn parse_level(line: &str) -> (Option<String>, String) {
    if let Some(m) = LEVEL_PATTERN.find(line) {
        let level = m.as_str().trim_matches('[').trim_matches(']').to_string();
        let remaining = format!("{}{}", &line[..m.start()], &line[m.end()..]);
        (Some(level), remaining)
    } else {
        (None, line.to_string())
    }
}

fn is_noise_line(line: &str) -> bool {
    let stripped = line.trim();
    if stripped.is_empty() {
        return true;
    }
    if stripped.starts_with("--") && stripped.ends_with("--") {
        return true;
    }
    false
}

fn set_coerced_value<'py>(
    dict: &Bound<'py, PyDict>,
    key: &str,
    v: &str,
) -> PyResult<()> {
    let py = dict.py();
    if v == "true" {
        dict.set_item(key, true)?;
    } else if v == "false" {
        dict.set_item(key, false)?;
    } else if let Ok(i) = v.parse::<i64>() {
        dict.set_item(key, i)?;
    } else if let Ok(f) = v.parse::<f64>() {
        dict.set_item(key, f)?;
    } else {
        dict.set_item(key, v)?;
    }
    let _ = py;
    Ok(())
}

fn parse_nested<'py>(py: Python<'py>, value: &str) -> PyResult<Bound<'py, PyDict>> {
    let inner = value.trim_start_matches('{').trim_end_matches('}');
    let mut parts: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut in_quotes = false;

    for ch in inner.chars() {
        if ch == '"' && !current.ends_with('\\') {
            in_quotes = !in_quotes;
            current.push(ch);
        } else if ch == ',' && !in_quotes {
            parts.push(current.trim().to_string());
            current = String::new();
        } else {
            current.push(ch);
        }
    }
    if !current.trim().is_empty() {
        parts.push(current.trim().to_string());
    }

    let dict = PyDict::new(py);
    for part in parts {
        if let Some(eq_pos) = part.find('=') {
            let k = &part[..eq_pos];
            let v = part[eq_pos + 1..].trim_matches('"');
            set_coerced_value(&dict, k, v)?;
        }
    }
    Ok(dict)
}

fn find_char(chars: &[char], start: usize, target: char) -> Option<usize> {
    for (offset, &ch) in chars[start..].iter().enumerate() {
        if ch == target {
            return Some(start + offset);
        }
    }
    None
}

fn parse_fields<'py>(py: Python<'py>, line: &str) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    let chars: Vec<char> = line.trim().chars().collect();
    let len = chars.len();
    let mut i = 0;

    while i < len {
        if chars[i] == ' ' || chars[i] == '\t' {
            i += 1;
            continue;
        }

        let eq_pos = match find_char(&chars, i, '=') {
            Some(pos) => pos,
            None => break,
        };

        let key: String = chars[i..eq_pos].iter().collect();
        let key = key.trim().to_string();

        if key.contains(' ') {
            match find_char(&chars, i, ' ') {
                Some(pos) => {
                    i = pos + 1;
                    continue;
                }
                None => break,
            }
        }

        i = eq_pos + 1;

        if i < len && chars[i] == '{' {
            let start = i;
            let mut brace_count = 1;
            i += 1;
            while i < len && brace_count > 0 {
                if chars[i] == '{' {
                    brace_count += 1;
                } else if chars[i] == '}' {
                    brace_count -= 1;
                }
                i += 1;
            }
            let nested_str: String = chars[start..i].iter().collect();
            let nested_val = parse_nested(py, &nested_str)?;
            dict.set_item(&key, nested_val)?;
        } else if i < len && chars[i] == '"' {
            i += 1;
            let start = i;
            while i < len && chars[i] != '"' {
                if chars[i] == '\\' && i + 1 < len {
                    i += 2;
                } else {
                    i += 1;
                }
            }
            let value: String = chars[start..i].iter().collect();
            dict.set_item(&key, value)?;
            if i < len {
                i += 1;
            }
        } else {
            let start = i;
            while i < len && chars[i] != ' ' && chars[i] != '\t' {
                i += 1;
            }
            let value: String = chars[start..i].iter().collect();
            if value.is_empty() {
                dict.set_item(&key, py.None())?;
            } else {
                set_coerced_value(&dict, &key, &value)?;
            }
        }
    }

    Ok(dict)
}

#[pyfunction]
fn parse_file<'py>(py: Python<'py>, path: &str) -> PyResult<Bound<'py, PyList>> {
    let content = fs::read_to_string(path).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            pyo3::exceptions::PyFileNotFoundError::new_err(format!(
                "No such file or directory: '{}'",
                path
            ))
        } else {
            pyo3::exceptions::PyOSError::new_err(e.to_string())
        }
    })?;

    let results = PyList::empty(py);

    for raw_line in content.lines() {
        if is_noise_line(raw_line) {
            continue;
        }

        let (ts_result, remaining) = parse_timestamp(raw_line);
        let (level, remaining) = parse_level(&remaining);

        if ts_result.is_none() && level.is_none() {
            continue;
        }

        let fields = parse_fields(py, &remaining)?;

        let entry = PyDict::new(py);

        match ts_result {
            Some(ts) => {
                let datetime_mod = py.import("datetime")?;
                let datetime_cls = datetime_mod.getattr("datetime")?;
                let py_ts = datetime_cls.call1((
                    ts.year,
                    ts.month,
                    ts.day,
                    ts.hour,
                    ts.minute,
                    ts.second,
                    ts.microsecond,
                ))?;
                entry.set_item("timestamp", py_ts)?;
            }
            None => {
                entry.set_item("timestamp", py.None())?;
            }
        }

        match &level {
            Some(l) => entry.set_item("level", l.as_str())?,
            None => entry.set_item("level", py.None())?,
        }

        entry.set_item("fields", &fields)?;
        entry.set_item("raw", raw_line)?;

        results.append(entry)?;
    }

    Ok(results)
}

#[pymodule]
fn _rust_log_parser(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_file, m)?)?;
    Ok(())
}
