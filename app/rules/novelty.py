from typing import Any
from uuid import UUID

from app.rules.base import AlertOutcome, AlertRule, EvaluationContext
from app.schemas.log import SearchFilters

_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


class NoveltyRule(AlertRule):
    """Fire when a new log cluster appears during the evaluation window."""

    def __init__(self, rule_id: UUID, application_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(rule_id, application_id, config)
        min_sev = config.get("min_severity", "WARNING").upper()
        self.min_severity_order = _LEVEL_ORDER.get(min_sev, 2)

    async def evaluate(self, ctx: EvaluationContext) -> AlertOutcome:
        new_clusters = await ctx.cluster_repo.find_created_after(
            app_id=self.application_id,
            since=ctx.window_start,
        )
        if new_clusters:
            return AlertOutcome.fire(
                payload={
                    "new_cluster_ids": [str(c.id) for c in new_clusters],
                    "representative_messages": [c.representative_message for c in new_clusters],
                },
                severity="warning",
            )
        return AlertOutcome.no_fire()
