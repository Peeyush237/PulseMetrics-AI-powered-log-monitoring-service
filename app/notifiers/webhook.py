from typing import Any

import httpx

from app.notifiers.base import AlertPayload, Notifier, NotificationResult


class WebhookNotifier(Notifier):
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.headers = headers or {}

    async def send(self, alert: AlertPayload) -> NotificationResult:
        payload: dict[str, Any] = {
            "rule_name": alert.rule_name,
            "rule_type": alert.rule_type,
            "application_name": alert.application_name,
            "fired_at": alert.fired_at,
            "severity": alert.severity,
            "details": alert.payload,
            "alert_event_id": alert.alert_event_id,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    self.url, json=payload, headers=self.headers
                )
                response.raise_for_status()
            return NotificationResult.ok()
        except httpx.HTTPError as exc:
            return NotificationResult.fail(str(exc))
