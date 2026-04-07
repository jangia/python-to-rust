import os
import tempfile

from log_parser import LogParser


def test_parse_info_log():
    line = '2024-01-15T10:23:45.123Z [INFO] service=auth request_id=abc-123 user_id=42 action=login duration_ms=150 status=success'

    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write(line + '\n')
        f.flush()
        path = f.name

    try:
        parser = LogParser()
        entries = parser.load(path)

        assert len(entries) == 1
        entry = entries[0]
        assert entry.level == "INFO"
        assert entry.fields["service"] == "auth"
        assert entry.fields["user_id"] == 42
        assert entry.fields["duration_ms"] == 150
    finally:
        os.unlink(path)
