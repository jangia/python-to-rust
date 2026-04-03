# Python to Rust

Example project demonstrating a Python-to-Rust rewrite of compute-heavy code. The project implements a messy log file parser that handles inconsistent formats, missing values, nested data, and noise lines.

## Setup

```bash
uv sync
```

## Usage

```python
from log_parser import LogParser

parser = LogParser()

# Parse a single line
entry = parser.parse_line('2024-01-15T10:23:45.123Z [INFO] service=auth user_id=42 duration_ms=150')

# Parse a file
entries = parser.parse_file("sample.log")

# Analytics
error_rates = parser.compute_error_rate_by_service(entries)
percentiles = parser.compute_duration_percentiles(entries)
top_users = parser.top_users_by_request_count(entries)
```

## Run tests

```bash
uv run pytest
```

## Log format

See `sample.log` for an example. The parser handles:

- Inconsistent timestamp formats (`2024-01-15T10:23:45.123Z`, `2024-01-15 10:23:46`, `2024/01/15 10:24:01`)
- Log level in different positions and formats (`[INFO]`, `ERROR`, `WARN`)
- Key-value fields with unquoted, quoted, and nested values (`status=success`, `error="timeout after 5000ms"`, `details={host="ldap-1.internal",port=636}`)
- Missing or empty values (`user_id=  `)
- Noise lines (`-- system restart at ... --`)
