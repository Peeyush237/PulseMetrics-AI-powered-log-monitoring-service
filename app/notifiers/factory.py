from typing import Any

from app.db.models.rule import NotificationChannel
from app.notifiers.base import Notifier
from app.notifiers.console import ConsoleNotifier
from app.notifiers.email import EmailNotifier
from app.notifiers.slack import SlackNotifier
from app.notifiers.webhook import WebhookNotifier


class NotifierFactory:
    @staticmethod
    def from_channel(channel: NotificationChannel) -> Notifier:
        config: dict[str, Any] = channel.config or {}
        ch_type = channel.channel_type

        if ch_type == "slack":
            return SlackNotifier(webhook_url=config["webhook_url"])
        elif ch_type == "email":
            return EmailNotifier(recipients=config.get("recipients", []))
        elif ch_type == "webhook":
            return WebhookNotifier(
                url=config["url"],
                headers=config.get("headers", {}),
            )
        else:
            return ConsoleNotifier()
