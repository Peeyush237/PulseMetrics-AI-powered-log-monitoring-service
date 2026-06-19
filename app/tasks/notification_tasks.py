import asyncio
import uuid
from typing import Any

import httpx

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.notifiers.base import AlertPayload
from app.notifiers.factory import NotifierFactory
from app.repositories.alert_repo import AlertRepository
from app.repositories.rule_repo import ChannelRepository, RuleRepository
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.tasks.notification_tasks.send_alert_notifications",
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    max_retries=5,
)
def send_alert_notifications(self: Any, alert_event_id: str) -> dict:
    return asyncio.get_event_loop().run_until_complete(
        _send_notifications_async(alert_event_id)
    )


async def _send_notifications_async(alert_event_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        alert_repo = AlertRepository(session)
        rule_repo = RuleRepository(session)
        channel_repo = ChannelRepository(session)

        event = await alert_repo.get(uuid.UUID(alert_event_id))
        if event is None:
            return {"error": "event not found"}

        rule = await rule_repo.get(event.rule_id)
        if rule is None:
            return {"error": "rule not found"}

        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from app.db.models.rule import AlertRule, RuleChannelBinding, NotificationChannel

        stmt = (
            select(NotificationChannel)
            .join(RuleChannelBinding, RuleChannelBinding.channel_id == NotificationChannel.id)
            .where(RuleChannelBinding.rule_id == rule.id)
        )
        result = await session.execute(stmt)
        channels = list(result.scalars().all())

        app_name = str(rule.application_id)
        try:
            from app.repositories.application_repo import ApplicationRepository
            app_repo = ApplicationRepository(session)
            app = await app_repo.get(rule.application_id)
            if app:
                app_name = app.name
        except Exception:
            pass

        payload = AlertPayload(
            rule_name=rule.name,
            rule_type=rule.rule_type,
            application_name=app_name,
            fired_at=event.fired_at.isoformat(),
            severity=event.severity,
            payload=event.payload,
            alert_event_id=str(event.id),
        )

        results: list[dict] = []
        for channel in channels:
            notifier = NotifierFactory.from_channel(channel)
            result_notif = await notifier.send(payload)
            results.append({"channel": str(channel.id), "success": result_notif.success})
            if not result_notif.success:
                logger.warning(
                    "notification_failed",
                    channel_id=str(channel.id),
                    error=result_notif.error,
                )

        return {"sent": len(results), "results": results}
