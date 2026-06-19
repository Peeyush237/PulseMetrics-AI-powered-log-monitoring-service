import re
from datetime import datetime, timezone

from dateutil.parser import parse as parse_date

from app.parsers.base import LogParser, ParsedLog

# RFC 5424 pattern (simplified but covers the key fields)
_RFC5424 = re.compile(
    r"<(?P<pri>\d+)>"
    r"(?P<version>\d+)\s+"
    r"(?P<timestamp>\S+)\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<appname>\S+)\s+"
    r"(?P<procid>\S+)\s+"
    r"(?P<msgid>\S+)\s+"
    r"(?P<structured_data>\S+)\s+"
    r"(?P<message>.+)$",
    re.DOTALL,
)

_SEVERITY_MAP = {
    0: "CRITICAL",  # Emergency
    1: "CRITICAL",  # Alert
    2: "CRITICAL",  # Critical
    3: "ERROR",     # Error
    4: "WARNING",   # Warning
    5: "WARNING",   # Notice
    6: "INFO",      # Informational
    7: "DEBUG",     # Debug
}


class SyslogParser(LogParser):
    def parse(self, raw: str) -> ParsedLog:
        m = _RFC5424.match(raw.strip())
        if not m:
            raise ValueError(f"Not a valid RFC 5424 syslog line: {raw[:80]}")

        pri = int(m.group("pri"))
        severity = pri % 8
        level = _SEVERITY_MAP.get(severity, "INFO")

        timestamp = datetime.now(timezone.utc)
        ts_str = m.group("timestamp")
        if ts_str and ts_str != "-":
            try:
                timestamp = parse_date(ts_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        appname = m.group("appname")
        service = appname if appname != "-" else None

        return ParsedLog(
            timestamp=timestamp,
            level=level,
            service=service,
            message=m.group("message").strip(),
            metadata={
                "hostname": m.group("hostname"),
                "procid": m.group("procid"),
                "msgid": m.group("msgid"),
            },
            raw=raw,
        )
