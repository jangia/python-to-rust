# Python to Rust

Example project demonstrating a step-by-step Python-to-Rust rewrite of a log file parser. Each branch represents a stage in the process, from initial Python implementation through contract testing to a full Rust port validated by property-based testing.

## Setup

```bash
uv sync
uv run maturin develop   # build the Rust extension
```

## Usage

Both implementations expose the same interface:

```python
from log_parser import LogParser
from rust_log_parser import RustLogParser

# Python implementation
entries = LogParser().load("sample.log")

# Rust implementation (same API, same results)
entries = RustLogParser().load("sample.log")
```

Each entry is a `LogEntry` with `timestamp`, `level`, `fields`, and `raw` attributes.

## Run tests

```bash
uv run pytest
```

## Log format

See `sample.log` for an example. The parser handles:

- Inconsistent timestamp formats (`2024-01-15T10:23:45.123Z`, `2024-01-15 10:23:46`, `2024/01/15 10:24:01`)
- Log level in different positions and formats (`[INFO]`, `ERROR`, `WARN`)
- Key-value fields with unquoted, quoted, and nested values (`status=success`, `error="timeout"`, `details={host="ldap-1.internal",port=636}`)
- Missing or empty values (`user_id=`)
- Noise lines (`-- system restart at ... --`)

## Branches

Each branch builds on the previous one. Together they show a progression from untested Python code to a dual-implementation project with strong correctness guarantees.

### `python-initial-state`

Starting point. Python `LogParser` implementation with a single basic test. The parser works but has minimal test coverage.

### `python-well-tested`

Adds a comprehensive test suite: 24 test functions (37 cases with parametrize) covering all timestamp formats, log levels, field types, nested objects, noise filtering, and edge cases. All tests are standalone functions using pytest fixtures.

### `python-contract-tests`

Restructures the tests into the **contract test pattern**. A `LogParserContract` base class holds all test methods with an abstract `parser` fixture. Two subclasses provide concrete implementations:

- `TestLogParserPython` -- passes (uses `LogParser`)
- `TestLogParserRust` -- fails (uses a placeholder `RustLogParser` that returns empty results)

This ensures that any future implementation must satisfy the exact same behavioral contract.

### `python-and-rust`

Implements the log parser in Rust as a PyO3 extension module (`_rust_log_parser`). A thin Python wrapper (`RustLogParser`) converts the Rust output into `LogEntry` objects. Both `TestLogParserPython` and `TestLogParserRust` now pass the same 37 contract tests.

### `python-and-rust-hypothesis`

Adds Hypothesis property-based testing. Custom strategies generate random log files with arbitrary timestamps, levels, field types, Unicode text, noise lines, and garbage. Two property tests (500 examples each) assert that Python and Rust produce identical results for any input. This caught a UTF-8 byte/char indexing bug in the Rust field parser that the hand-written contract tests missed.
