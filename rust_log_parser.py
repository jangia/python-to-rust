import _rust_log_parser
from log_parser import LogEntry


class RustLogParser:

    def load(self, path: str) -> list[LogEntry]:
        raw_entries = _rust_log_parser.parse_file(path)
        return [
            LogEntry(
                timestamp=entry["timestamp"],
                level=entry["level"],
                fields=dict(entry["fields"]),
                raw=entry["raw"],
            )
            for entry in raw_entries
        ]
