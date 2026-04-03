from log_parser import LogParser


def test_parse_info_log():
    parser = LogParser()
    line = '2024-01-15T10:23:45.123Z [INFO] service=auth request_id=abc-123 user_id=42 action=login duration_ms=150 status=success'
    entry = parser.parse_line(line)

    assert entry is not None
    assert entry.level == "INFO"
    assert entry.fields["service"] == "auth"
    assert entry.fields["user_id"] == 42
    assert entry.fields["duration_ms"] == 150
