import os
import tempfile
from datetime import datetime

import pytest

from log_parser import LogParser


@pytest.fixture
def create_log_file():
    paths = []

    def _create(*lines: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for line in lines:
                f.write(line + "\n")
            paths.append(f.name)
        return paths[-1]

    yield _create

    for path in paths:
        os.unlink(path)


@pytest.fixture
def parser():
    return LogParser()


# --- Timestamp formats (parametrized) ---


@pytest.mark.parametrize(
    "line, expected_ts",
    [
        (
            "2024-01-15T10:23:45.123Z [INFO] service=auth",
            datetime(2024, 1, 15, 10, 23, 45, 123000),
        ),
        (
            "2024-01-15T10:23:45Z [INFO] service=auth",
            datetime(2024, 1, 15, 10, 23, 45),
        ),
        (
            "2024-01-15 10:23:45 [INFO] service=auth",
            datetime(2024, 1, 15, 10, 23, 45),
        ),
        (
            "2024/01/15 10:23:45 [INFO] service=auth",
            datetime(2024, 1, 15, 10, 23, 45),
        ),
    ],
    ids=[
        "iso8601_fractional",
        "iso8601_no_fractional",
        "datetime_dashes",
        "datetime_slashes",
    ],
)
def test_timestamp_formats(parser, create_log_file, line, expected_ts):
    path = create_log_file(line)
    entries = parser.load(path)
    assert len(entries) == 1
    assert entries[0].timestamp == expected_ts


# --- All log levels ---


@pytest.mark.parametrize("level", ["INFO", "ERROR", "WARN", "DEBUG", "TRACE", "FATAL"])
def test_all_levels(parser, create_log_file, level):
    path = create_log_file(f"2024-01-15T10:23:45Z [{level}] service=app")
    entries = parser.load(path)
    assert len(entries) == 1
    assert entries[0].level == level


@pytest.mark.parametrize("level", ["INFO", "ERROR", "WARN", "DEBUG", "TRACE", "FATAL"])
def test_level_without_brackets(parser, create_log_file, level):
    path = create_log_file(f"2024-01-15T10:23:45Z {level} service=app")
    entries = parser.load(path)
    assert entries[0].level == level


# --- Nested field parsing ---


def test_nested_fields(parser, create_log_file):
    path = create_log_file(
        '2024-01-15T10:23:45Z [ERROR] details={host="ldap-1.internal",port=636,ssl=true}'
    )
    entries = parser.load(path)
    assert len(entries) == 1
    details = entries[0].fields["details"]
    assert details["host"] == "ldap-1.internal"
    assert details["port"] == 636
    assert details["ssl"] is True


def test_nested_fields_with_false(parser, create_log_file):
    path = create_log_file(
        "2024-01-15T10:23:45Z [INFO] config={debug=false,retries=3}"
    )
    entries = parser.load(path)
    config = entries[0].fields["config"]
    assert config["debug"] is False
    assert config["retries"] == 3


def test_nested_fields_with_float(parser, create_log_file):
    path = create_log_file(
        "2024-01-15T10:23:45Z [INFO] stats={avg=12.5,count=100}"
    )
    entries = parser.load(path)
    stats = entries[0].fields["stats"]
    assert stats["avg"] == 12.5
    assert stats["count"] == 100


# --- Noise lines ignored ---


def test_empty_lines_ignored(parser, create_log_file):
    path = create_log_file(
        "2024-01-15T10:23:45Z [INFO] service=auth",
        "",
        "   ",
        "2024-01-15T10:23:46Z [ERROR] service=payment",
    )
    entries = parser.load(path)
    assert len(entries) == 2


def test_separator_lines_ignored(parser, create_log_file):
    path = create_log_file(
        "2024-01-15T10:23:45Z [INFO] service=auth",
        "-- system restart at 2024-01-15T10:24:00Z --",
        "2024-01-15T10:23:46Z [ERROR] service=payment",
    )
    entries = parser.load(path)
    assert len(entries) == 2


def test_line_without_timestamp_or_level_ignored(parser, create_log_file):
    path = create_log_file("just some random text with no structure")
    entries = parser.load(path)
    assert len(entries) == 0


# --- Field types ---


def test_string_fields(parser, create_log_file):
    path = create_log_file(
        '2024-01-15T10:23:45Z [INFO] msg="hello world" service=auth'
    )
    entries = parser.load(path)
    assert entries[0].fields["msg"] == "hello world"
    assert entries[0].fields["service"] == "auth"


def test_quoted_string_with_escaped_quotes(parser, create_log_file):
    path = create_log_file(
        r'2024-01-15T10:23:45Z [ERROR] error="failed to parse \"config.json\"" service=app'
    )
    entries = parser.load(path)
    assert "config.json" in entries[0].fields["error"]


def test_integer_field(parser, create_log_file):
    path = create_log_file("2024-01-15T10:23:45Z [INFO] duration_ms=150 user_id=42")
    entries = parser.load(path)
    assert entries[0].fields["duration_ms"] == 150


def test_float_field(parser, create_log_file):
    path = create_log_file("2024-01-15T10:23:45Z [INFO] amount=99.99")
    entries = parser.load(path)
    assert entries[0].fields["amount"] == 99.99


def test_boolean_fields(parser, create_log_file):
    path = create_log_file("2024-01-15T10:23:45Z [INFO] success=true failed=false")
    entries = parser.load(path)
    assert entries[0].fields["success"] is True
    assert entries[0].fields["failed"] is False


def test_empty_value_field(parser, create_log_file):
    path = create_log_file("2024-01-15T10:23:45Z [INFO] user_id= service=auth")
    entries = parser.load(path)
    assert entries[0].fields["user_id"] is None


def test_mixed_field_types_in_one_line(parser, create_log_file):
    path = create_log_file(
        '2024-01-15T10:23:45Z [INFO] service=auth user_id=42 amount=9.99 success=true msg="ok"'
    )
    entries = parser.load(path)
    fields = entries[0].fields
    assert fields["service"] == "auth"
    assert fields["user_id"] == 42
    assert fields["amount"] == 9.99
    assert fields["success"] is True
    assert fields["msg"] == "ok"


# --- Multiline files ---


def test_multiline_file(parser, create_log_file):
    path = create_log_file(
        "2024-01-15T10:23:45.123Z [INFO] service=auth user_id=42 action=login duration_ms=150 status=success",
        '[ERROR] 2024-01-15T10:23:45.456Z service=payment action=charge amount=99.99 error="timeout"',
        "2024-01-15 10:23:46 WARN service=auth retry_count=3",
        '2024-01-15T10:23:47.001Z [DEBUG] service=gateway msg="Health check passed"',
        "",
        "-- separator --",
        "2024/01/15 10:24:01 [INFO] service=gateway action=startup",
    )
    entries = parser.load(path)
    assert len(entries) == 5
    assert entries[0].level == "INFO"
    assert entries[1].level == "ERROR"
    assert entries[2].level == "WARN"
    assert entries[3].level == "DEBUG"
    assert entries[4].level == "INFO"


def test_timestamp_after_level(parser, create_log_file):
    path = create_log_file(
        "[ERROR] 2024-01-15T10:23:45.456Z service=payment"
    )
    entries = parser.load(path)
    assert len(entries) == 1
    assert entries[0].level == "ERROR"
    assert entries[0].timestamp == datetime(2024, 1, 15, 10, 23, 45, 456000)


def test_raw_line_preserved(parser, create_log_file):
    line = "2024-01-15T10:23:45Z [INFO] service=auth"
    path = create_log_file(line)
    entries = parser.load(path)
    assert entries[0].raw == line
