from datetime import timedelta
from typing import Any
from uuid import UUID

from app.rules.base import AlertOutcome, AlertRule, EvaluationContext
from app.schemas.log import SearchFilters


class RateOfChangeRule(AlertRule):
    """Fire when count rate increases by more than X% vs the previous equal window."""

    def __init__(self, rule_id: UUID, application_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(rule_id, application_id, config)
        self.threshold_pct: float = float(config.get("threshold_pct", 100.0))
        filters_raw: dict[str, Any] = config.get("filters", {})
        self.filters = SearchFilters(
            level=filters_raw.get("level"),
            service=(
                filters_raw.get("service")
                if isinstance(filters_raw.get("service"), list)
                else ([filters_raw["service"]] if filters_raw.get("service") else None)
            ),
        )

    async def evaluate(self, ctx: EvaluationContext) -> AlertOutcome:
        window_duration = ctx.window_end - ctx.window_start
        prev_start = ctx.window_start - window_duration
        prev_end = ctx.window_start

        current_count = await ctx.log_repo.count_matching(
            application_id=self.application_id,
            filters=self.filters,
            window_start=ctx.window_start,
            window_end=ctx.window_end,
        )
        previous_count = await ctx.log_repo.count_matching(
            application_id=self.application_id,
            filters=self.filters,
            window_start=prev_start,
            window_end=prev_end,
        )

        if previous_count == 0:
            return AlertOutcome.no_fire()

        change_pct = ((current_count - previous_count) / previous_count) * 100
        if change_pct > self.threshold_pct:
            return AlertOutcome.fire(
                payload={
                    "current_count": current_count,
                    "previous_count": previous_count,
                    "change_pct": round(change_pct, 1),
                    "threshold_pct": self.threshold_pct,
                },
                severity="warning",
            )
        return AlertOutcome.no_fire()
