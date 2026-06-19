import re
from datetime import datetime, timezone

from dateutil.parser import parse as parse_date, ParserError

from app.parsers.base import LogParser, ParsedLog

_LEVEL_RE = re.compile(
    r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL|NOTICE)\b", re.IGNORECASE
)
_TIMESTAMP_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"),
    re.compile(r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}"),
    re.compile(r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"),
]

_LEVEL_MAP = {"WARN": "WARNING", "FATAL": "CRITICAL", "NOTICE": "INFO"}


class PlainTextParser(LogParser):
    def parse(self, raw: str) -> ParsedLog:
        line = raw.strip()
        if not line:
            raise ValueError("Empty log line")

        timestamp = datetime.now(timezone.utc)
        remaining = line

        for pattern in _TIMESTAMP_PATTERNS:
            m = pattern.search(remaining)
            if m:
                try:
                    timestamp = parse_date(m.group())
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    remaining = (remaining[: m.start()] + remaining[m.end() :]).strip()
                    break
                except ParserError:
                    pass

        level = "INFO"
        m = _LEVEL_RE.search(remaining)
        if m:
            raw_level = m.group().upper()
            level = _LEVEL_MAP.get(raw_level, raw_level)
            remaining = (remaining[: m.start()] + remaining[m.end() :]).strip()

        message = remaining.strip("[]| :-") or line

        return ParsedLog(
            timestamp=timestamp,
            level=level,
            message=message,
            raw=raw,
        )
