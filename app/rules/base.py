from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.repositories.cluster_repo import ClusterRepository
from app.repositories.log_repo import LogRepository


@dataclass
class EvaluationContext:
    log_repo: LogRepository
    cluster_repo: ClusterRepository
    window_start: datetime
    window_end: datetime
    application_id: UUID


@dataclass
class AlertOutcome:
    fired: bool
    payload: dict[str, Any] = field(default_factory=dict)
    sample_log_ids: list[int] = field(default_factory=list)
    severity: str = "warning"

    @classmethod
    def fire(
        cls,
        payload: dict[str, Any],
        sample_log_ids: list[int] | None = None,
        severity: str = "warning",
    ) -> "AlertOutcome":
        return cls(
            fired=True,
            payload=payload,
            sample_log_ids=sample_log_ids or [],
            severity=severity,
        )

    @classmethod
    def no_fire(cls) -> "AlertOutcome":
        return cls(fired=False)


class AlertRule(ABC):
    def __init__(self, rule_id: UUID, application_id: UUID, config: dict[str, Any]) -> None:
        self.rule_id = rule_id
        self.application_id = application_id
        self.config = config

    @abstractmethod
    async def evaluate(self, ctx: EvaluationContext) -> AlertOutcome:
        """Evaluate the rule against the context window. Return AlertOutcome."""
