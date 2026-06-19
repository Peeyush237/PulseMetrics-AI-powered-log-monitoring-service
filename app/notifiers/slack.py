import httpx

from app.notifiers.base import AlertPayload, Notifier, NotificationResult

_SEVERITY_COLORS = {"critical": "#FF0000", "warning": "#FFA500", "info": "#36A64F"}


class SlackNotifier(Notifier):
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def send(self, alert: AlertPayload) -> NotificationResult:
        color = _SEVERITY_COLORS.get(alert.severity, "#808080")
        message = {
            "attachments": [
                {
                    "color": color,
                    "title": f"🚨 [{alert.application_name}] {alert.rule_name}",
                    "fields": [
                        {"title": "Rule type", "value": alert.rule_type, "short": True},
                        {"title": "Severity", "value": alert.severity.upper(), "short": True},
                        {"title": "Fired at", "value": alert.fired_at, "short": True},
                        {
                            "title": "Details",
                            "value": "\n".join(
                                f"{k}: {v}" for k, v in alert.payload.items()
                            ),
                            "short": False,
                        },
                    ],
                    "footer": "PulseMetrics",
                    "actions": (
                        [{"type": "button", "text": "View in dashboard", "url": alert.dashboard_url}]
                        if alert.dashboard_url
                        else []
                    ),
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self.webhook_url, json=message)
                response.raise_for_status()
            return NotificationResult.ok()
        except httpx.HTTPError as exc:
            return NotificationResult.fail(str(exc))
