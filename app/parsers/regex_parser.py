import re
from datetime import datetime, timezone

from dateutil.parser import parse as parse_date

from app.parsers.base import LogParser, ParsedLog


class RegexParser(LogParser):
    def __init__(self, pattern: str, field_map: dict[str, str] | None = None) -> None:
        self.pattern = re.compile(pattern)
        # field_map: group_name -> parsed field (timestamp/level/service/message)
        self.field_map = field_map or {}

    def parse(self, raw: str) -> ParsedLog:
        m = self.pattern.match(raw.strip())
        if not m:
            raise ValueError(f"Line does not match regex pattern: {raw[:80]}")

        groups = m.groupdict()
        mapped: dict[str, str] = {}
        metadata: dict[str, str] = {}

        for group, value in groups.items():
            target = self.field_map.get(group, group)
            if target in {"timestamp", "level", "service", "message"}:
                mapped[target] = value
            else:
                metadata[group] = value

        if "message" not in mapped:
            raise ValueError("Regex pattern must capture a 'message' group")

        timestamp = datetime.now(timezone.utc)
        if ts_str := mapped.get("timestamp"):
            try:
                timestamp = parse_date(ts_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        return ParsedLog(
            timestamp=timestamp,
            level=mapped.get("level", "INFO").upper(),
            service=mapped.get("service"),
            message=mapped["message"],
            metadata=metadata,
            raw=raw,
        )
