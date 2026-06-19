from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ParsedLog:
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    level: str = "INFO"
    service: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: str | None = None


class LogParser(ABC):
    @abstractmethod
    def parse(self, raw: str) -> ParsedLog:
        """Parse a raw log string into a ParsedLog. Raise ValueError on parse failure."""
