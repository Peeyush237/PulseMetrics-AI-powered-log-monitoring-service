import asyncio
from typing import Any

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services.rule_evaluator import RuleEvaluator
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.rule_tasks.evaluate_all_rules")
def evaluate_all_rules() -> dict:
    return asyncio.get_event_loop().run_until_complete(_evaluate_all_async())


async def _evaluate_all_async() -> dict:
    async with AsyncSessionLocal() as session:
        evaluator = RuleEvaluator(session)
        events = await evaluator.run_all()
        fired_count = len(events)
        if fired_count:
            logger.info("rules_evaluated", fired_count=fired_count)
            # Dispatch notifications for each fired event
            for event in events:
                from app.tasks.notification_tasks import send_alert_notifications
                send_alert_notifications.delay(str(event.id))
        return {"fired": fired_count}
