from app.db.models.application import Application
from app.parsers.base import LogParser
from app.parsers.json_parser import JSONParser
from app.parsers.plaintext_parser import PlainTextParser
from app.parsers.regex_parser import RegexParser
from app.parsers.syslog_parser import SyslogParser


class ParserFactory:
    @staticmethod
    def from_application(app: Application) -> LogParser:
        parser_type = app.parser_type.lower()
        config: dict = app.parser_config or {}

        if parser_type == "json":
            return JSONParser()
        elif parser_type == "syslog":
            return SyslogParser()
        elif parser_type == "regex":
            pattern = config.get("pattern", r"(?P<message>.+)")
            field_map = config.get("field_map", {})
            return RegexParser(pattern=pattern, field_map=field_map)
        else:
            return PlainTextParser()

    @staticmethod
    def from_type(parser_type: str, config: dict | None = None) -> LogParser:
        config = config or {}
        if parser_type == "json":
            return JSONParser()
        elif parser_type == "syslog":
            return SyslogParser()
        elif parser_type == "regex":
            return RegexParser(
                pattern=config.get("pattern", r"(?P<message>.+)"),
                field_map=config.get("field_map", {}),
            )
        return PlainTextParser()
