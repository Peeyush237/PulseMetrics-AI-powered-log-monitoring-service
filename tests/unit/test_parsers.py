import pytest
from app.parsers.json_parser import JSONParser
from app.parsers.plaintext_parser import PlainTextParser
from app.parsers.syslog_parser import SyslogParser
from app.parsers.regex_parser import RegexParser


class TestJSONParser:
    def test_basic(self):
        p = JSONParser()
        log = p.parse('{"message": "Hello world", "level": "ERROR", "service": "api"}')
        assert log.message == "Hello world"
        assert log.level == "ERROR"
        assert log.service == "api"

    def test_metadata_extracted(self):
        p = JSONParser()
        log = p.parse('{"message": "test", "user_id": 123, "trace_id": "abc"}')
        assert log.metadata["user_id"] == 123
        assert log.metadata["trace_id"] == "abc"

    def test_missing_message_raises(self):
        p = JSONParser()
        with pytest.raises(ValueError, match="message"):
            p.parse('{"level": "INFO"}')

    def test_invalid_json_raises(self):
        p = JSONParser()
        with pytest.raises(ValueError, match="Invalid JSON"):
            p.parse("not json at all")

    def test_timestamp_parsed(self):
        p = JSONParser()
        log = p.parse('{"message": "hi", "timestamp": "2026-01-15T10:30:00Z"}')
        assert log.timestamp.year == 2026
        assert log.timestamp.month == 1


class TestPlainTextParser:
    def test_level_extracted(self):
        p = PlainTextParser()
        log = p.parse("2026-01-15 10:30:00 ERROR Connection failed")
        assert log.level == "ERROR"

    def test_warning_normalized(self):
        p = PlainTextParser()
        log = p.parse("WARN something happened")
        assert log.level == "WARNING"

    def test_fatal_normalized(self):
        p = PlainTextParser()
        log = p.parse("FATAL system crash")
        assert log.level == "CRITICAL"

    def test_empty_raises(self):
        p = PlainTextParser()
        with pytest.raises(ValueError, match="Empty"):
            p.parse("")


class TestSyslogParser:
    def test_valid_rfc5424(self):
        p = SyslogParser()
        line = "<34>1 2026-01-15T10:30:00Z myhostname myapp 1234 - - Connection to db failed"
        log = p.parse(line)
        assert log.level == "ERROR"
        assert log.service == "myapp"
        assert "Connection" in log.message

    def test_invalid_raises(self):
        p = SyslogParser()
        with pytest.raises(ValueError):
            p.parse("not a syslog line")


class TestRegexParser:
    def test_basic_pattern(self):
        p = RegexParser(
            pattern=r"(?P<timestamp>\d{4}-\d{2}-\d{2}) (?P<level>\w+) (?P<message>.+)",
        )
        log = p.parse("2026-01-15 ERROR Payment declined")
        assert log.level == "ERROR"
        assert log.message == "Payment declined"

    def test_missing_message_group_raises(self):
        with pytest.raises(Exception):
            p = RegexParser(pattern=r"(?P<level>\w+)")
            p.parse("ERROR something")
