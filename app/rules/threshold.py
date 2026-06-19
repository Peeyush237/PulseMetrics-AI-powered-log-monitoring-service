from typing import Any
from uuid import UUID

from app.rules.base import AlertOutcome, AlertRule, EvaluationContext
from app.schemas.log import SearchFilters


class ThresholdRule(AlertRule):
    """Fire when count of matching logs in time window exceeds threshold."""

    def __init__(self, rule_id: UUID, application_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(rule_id, application_id, config)
        self.threshold: int = config.get("threshold", 10)
        self.window_seconds: int = config.get("window_seconds", 300)
        filters_raw: dict[str, Any] = config.get("filters", {})
        self.filters = SearchFilters(
            level=filters_raw.get("level"),
            service=filters_raw.get("service") if isinstance(filters_raw.get("service"), list)
                    else ([filters_raw["service"]] if filters_raw.get("service") else None),
            message_contains=filters_raw.get("message_contains"),
            metadata=filters_raw.get("metadata"),
        )

    async def evaluate(self, ctx: EvaluationContext) -> AlertOutcome:
        count = await ctx.log_repo.count_matching(
            application_id=self.application_id,
            filters=self.filters,
            window_start=ctx.window_start,
            window_end=ctx.window_end,
        )
        if count > self.threshold:
            samples = await ctx.log_repo.sample_matching(
                application_id=self.application_id,
                filters=self.filters,
                window_start=ctx.window_start,
                window_end=ctx.window_end,
                limit=5,
            )
            return AlertOutcome.fire(
                payload={"count": count, "threshold": self.threshold},
                sample_log_ids=[s.id for s in samples],
                severity="warning" if count < self.threshold * 2 else "critical",
            )
        return AlertOutcome.no_fire()
