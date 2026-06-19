from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.alert import AlertEvent
from app.db.models.rule import AlertRule as AlertRuleModel
from app.repositories.alert_repo import AlertRepository
from app.repositories.cluster_repo import ClusterRepository
from app.repositories.log_repo import LogRepository
from app.repositories.rule_repo import RuleRepository
from app.rules.base import EvaluationContext
from app.rules.factory import RuleFactory

logger = get_logger(__name__)


class RuleEvaluator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rule_repo = RuleRepository(session)
        self.log_repo = LogRepository(session)
        self.cluster_repo = ClusterRepository(session)
        self.alert_repo = AlertRepository(session)

    async def evaluate_rule(self, rule_model: AlertRuleModel) -> AlertEvent | None:
        now = datetime.now(timezone.utc)

        # Enforce cooldown
        if rule_model.last_fired_at:
            elapsed = (now - rule_model.last_fired_at).total_seconds()
            if elapsed < rule_model.cooldown_seconds:
                return None

        window_seconds = rule_model.config.get("window_seconds", 300)
        window_start = now - timedelta(seconds=window_seconds)

        rule = RuleFactory.from_db(
            rule_id=rule_model.id,
            rule_type=rule_model.rule_type,
            application_id=rule_model.application_id,
            config=rule_model.config,
        )

        ctx = EvaluationContext(
            log_repo=self.log_repo,
            cluster_repo=self.cluster_repo,
            window_start=window_start,
            window_end=now,
            application_id=rule_model.application_id,
        )

        try:
            outcome = await rule.evaluate(ctx)
        except Exception as exc:
            logger.error("rule_evaluation_failed", rule_id=str(rule_model.id), error=str(exc))
            return None

        if not outcome.fired:
            return None

        event = AlertEvent(
            rule_id=rule_model.id,
            severity=outcome.severity,
            payload=outcome.payload,
            sample_log_ids=outcome.sample_log_ids or None,
        )
        self.session.add(event)
        await self.rule_repo.update_last_fired(rule_model.id, now)
        await self.session.commit()

        logger.info(
            "alert_fired",
            rule_id=str(rule_model.id),
            rule_name=rule_model.name,
            severity=outcome.severity,
        )
        return event

    async def run_all(self) -> list[AlertEvent]:
        rules = await self.rule_repo.list_enabled()
        events: list[AlertEvent] = []
        for rule_model in rules:
            event = await self.evaluate_rule(rule_model)
            if event:
                events.append(event)
        return events
