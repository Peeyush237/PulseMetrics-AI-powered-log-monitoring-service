from datetime import timedelta
from typing import Any
from uuid import UUID

import numpy as np

from app.rules.base import AlertOutcome, AlertRule, EvaluationContext
from app.schemas.log import SearchFilters


class AnomalyRule(AlertRule):
    """Fire when current window count exceeds mean + N*stddev of baseline hours."""

    def __init__(self, rule_id: UUID, application_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(rule_id, application_id, config)
        self.baseline_hours: int = config.get("baseline_hours", 24)
        self.sensitivity_stddev: float = float(config.get("sensitivity_stddev", 3.0))
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
        baseline_counts: list[int] = []

        for i in range(self.baseline_hours):
            hour_end = ctx.window_start - timedelta(hours=i)
            hour_start = hour_end - window_duration
            count = await ctx.log_repo.count_matching(
                application_id=self.application_id,
                filters=self.filters,
                window_start=hour_start,
                window_end=hour_end,
            )
            baseline_counts.append(count)

        if len(baseline_counts) < 3:
            return AlertOutcome.no_fire()

        arr = np.array(baseline_counts, dtype=float)
        mean = float(np.mean(arr))
        stddev = float(np.std(arr))

        current_count = await ctx.log_repo.count_matching(
            application_id=self.application_id,
            filters=self.filters,
            window_start=ctx.window_start,
            window_end=ctx.window_end,
        )

        threshold = mean + self.sensitivity_stddev * stddev
        if current_count > threshold:
            return AlertOutcome.fire(
                payload={
                    "current_count": current_count,
                    "baseline_mean": round(mean, 2),
                    "baseline_stddev": round(stddev, 2),
                    "threshold": round(threshold, 2),
                    "sensitivity_stddev": self.sensitivity_stddev,
                },
                severity="warning",
            )
        return AlertOutcome.no_fire()
