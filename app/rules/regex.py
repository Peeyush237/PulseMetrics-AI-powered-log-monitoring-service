import re
from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from app.db.models.log import Log
from app.rules.base import AlertOutcome, AlertRule, EvaluationContext


class RegexRule(AlertRule):
    """Fire when any log message in the window matches a regex pattern."""

    def __init__(self, rule_id: UUID, application_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(rule_id, application_id, config)
        pattern = config.get("pattern", "")
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE
        self.pattern = re.compile(pattern, flags)

    async def evaluate(self, ctx: EvaluationContext) -> AlertOutcome:
        stmt = (
            select(Log)
            .where(
                Log.application_id == self.application_id,
                Log.timestamp >= ctx.window_start,
                Log.timestamp <= ctx.window_end,
            )
            .order_by(Log.timestamp.desc())
            .limit(500)
        )
        result = await ctx.log_repo.session.execute(stmt)
        logs = list(result.scalars().all())

        matched = [l for l in logs if self.pattern.search(l.message)]
        if matched:
            return AlertOutcome.fire(
                payload={
                    "pattern": self.config.get("pattern"),
                    "match_count": len(matched),
                },
                sample_log_ids=[m.id for m in matched[:5]],
                severity="warning",
            )
        return AlertOutcome.no_fire()
