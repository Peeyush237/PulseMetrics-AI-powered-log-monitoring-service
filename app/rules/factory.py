from typing import Any
from uuid import UUID

from app.rules.anomaly import AnomalyRule
from app.rules.base import AlertRule
from app.rules.novelty import NoveltyRule
from app.rules.rate_of_change import RateOfChangeRule
from app.rules.regex import RegexRule
from app.rules.threshold import ThresholdRule

_RULE_CLASSES: dict[str, type[AlertRule]] = {
    "threshold": ThresholdRule,
    "regex": RegexRule,
    "novelty": NoveltyRule,
    "rate_of_change": RateOfChangeRule,
    "anomaly": AnomalyRule,
}


class RuleFactory:
    @staticmethod
    def from_db(
        rule_id: UUID,
        rule_type: str,
        application_id: UUID,
        config: dict[str, Any],
    ) -> AlertRule:
        cls = _RULE_CLASSES.get(rule_type)
        if cls is None:
            raise ValueError(f"Unknown rule type: {rule_type}")
        return cls(rule_id=rule_id, application_id=application_id, config=config)
