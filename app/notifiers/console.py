import json

from app.core.logging import get_logger
from app.notifiers.base import AlertPayload, Notifier, NotificationResult

logger = get_logger(__name__)


class ConsoleNotifier(Notifier):
    async def send(self, alert: AlertPayload) -> NotificationResult:
        logger.warning(
            "alert_fired",
            rule_name=alert.rule_name,
            application=alert.application_name,
            severity=alert.severity,
            payload=alert.payload,
        )
        return NotificationResult.ok()
