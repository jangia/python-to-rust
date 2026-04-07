import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class LogEntry:
    timestamp: Optional[datetime]
    level: Optional[str]
    fields: dict = field(default_factory=dict)
    raw: str = ""


class LogParser:
    TIMESTAMP_PATTERNS = [
        (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", "%Y-%m-%dT%H:%M:%S.%fZ"),
        (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "%Y-%m-%dT%H:%M:%SZ"),
        (r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "%Y-%m-%d %H:%M:%S"),
        (r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", "%Y/%m/%d %H:%M:%S"),
    ]

    LEVEL_PATTERN = re.compile(r"\[?(INFO|ERROR|WARN|DEBUG|TRACE|FATAL)\]?")

    def load(self, path: str) -> list[LogEntry]:
        entries = []
        with open(path) as f:
            for line in f:
                entry = self._parse_line(line.rstrip("\n"))
                if entry is not None:
                    entries.append(entry)
        return entries

    def _parse_timestamp(self, line: str) -> tuple[Optional[datetime], str]:
        for pattern, fmt in self.TIMESTAMP_PATTERNS:
            match = re.search(pattern, line)
            if match:
                ts = datetime.strptime(match.group(), fmt)
                remaining = line[:match.start()] + line[match.end():]
                return ts, remaining
        return None, line

    def _parse_level(self, line: str) -> tuple[Optional[str], str]:
        match = self.LEVEL_PATTERN.search(line)
        if match:
            level = match.group().strip("[]")
            remaining = line[:match.start()] + line[match.end():]
            return level, remaining
        return None, line

    def _parse_nested(self, value: str) -> dict:
        result = {}
        inner = value.strip("{}")
        parts = []
        current = ""
        in_quotes = False

        for char in inner:
            if char == '"' and (not current or current[-1] != "\\"):
                in_quotes = not in_quotes
                current += char
            elif char == "," and not in_quotes:
                parts.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current.strip())

        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                v = v.strip('"')
                if v == "true":
                    result[k] = True
                elif v == "false":
                    result[k] = False
                else:
                    try:
                        result[k] = int(v)
                    except ValueError:
                        try:
                            result[k] = float(v)
                        except ValueError:
                            result[k] = v
        return result

    def _parse_fields(self, line: str) -> dict:
        fields = {}
        i = 0
        line = line.strip()

        while i < len(line):
            if line[i] in (" ", "\t"):
                i += 1
                continue

            eq_pos = line.find("=", i)
            if eq_pos == -1:
                break

            key = line[i:eq_pos].strip()
            if " " in key:
                i = line.find(" ", i) + 1
                if i == 0:
                    break
                continue

            i = eq_pos + 1

            if i < len(line) and line[i] == "{":
                brace_count = 1
                start = i
                i += 1
                while i < len(line) and brace_count > 0:
                    if line[i] == "{":
                        brace_count += 1
                    elif line[i] == "}":
                        brace_count -= 1
                    i += 1
                fields[key] = self._parse_nested(line[start:i])
            elif i < len(line) and line[i] == '"':
                i += 1
                start = i
                while i < len(line) and line[i] != '"':
                    if line[i] == "\\" and i + 1 < len(line):
                        i += 2
                    else:
                        i += 1
                fields[key] = line[start:i]
                if i < len(line):
                    i += 1
            else:
                start = i
                while i < len(line) and line[i] not in (" ", "\t"):
                    i += 1
                value = line[start:i]
                if not value:
                    fields[key] = None
                elif value == "true":
                    fields[key] = True
                elif value == "false":
                    fields[key] = False
                else:
                    try:
                        fields[key] = int(value)
                    except ValueError:
                        try:
                            fields[key] = float(value)
                        except ValueError:
                            fields[key] = value

        return fields

    def _is_noise_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if stripped.startswith("--") and stripped.endswith("--"):
            return True
        return False

    def _parse_line(self, line: str) -> Optional[LogEntry]:
        if self._is_noise_line(line):
            return None

        timestamp, remaining = self._parse_timestamp(line)
        level, remaining = self._parse_level(remaining)

        if timestamp is None and level is None:
            return None

        fields = self._parse_fields(remaining)

        return LogEntry(
            timestamp=timestamp,
            level=level,
            fields=fields,
            raw=line,
        )

