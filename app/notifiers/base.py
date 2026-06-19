from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class NotificationResult:
    success: bool
    error: str | None = None

    @classmethod
    def ok(cls) -> "NotificationResult":
        return cls(success=True)

    @classmethod
    def fail(cls, error: str) -> "NotificationResult":
        return cls(success=False, error=error)


@dataclass
class AlertPayload:
    rule_name: str
    rule_type: str
    application_name: str
    fired_at: str
    severity: str
    payload: dict[str, Any]
    alert_event_id: str
    dashboard_url: str = ""


class Notifier(ABC):
    @abstractmethod
    async def send(self, alert: AlertPayload) -> NotificationResult:
        """Send a notification. Raise on non-retriable errors, return Result otherwise."""
