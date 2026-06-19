import json
from datetime import datetime, timezone

from dateutil.parser import parse as parse_date

from app.parsers.base import LogParser, ParsedLog

_RESERVED = {"timestamp", "level", "service", "message"}


class JSONParser(LogParser):
    def parse(self, raw: str) -> ParsedLog:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

        if "message" not in data:
            raise ValueError("JSON log must contain a 'message' field")

        timestamp = datetime.now(timezone.utc)
        if ts := data.get("timestamp"):
            try:
                timestamp = parse_date(str(ts))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        metadata = {k: v for k, v in data.items() if k not in _RESERVED}

        return ParsedLog(
            timestamp=timestamp,
            level=str(data.get("level", "INFO")).upper(),
            service=data.get("service"),
            message=str(data["message"]),
            metadata=metadata,
            raw=raw,
        )
