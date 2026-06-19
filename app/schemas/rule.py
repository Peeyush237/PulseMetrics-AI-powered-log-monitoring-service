import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


RuleType = Literal["threshold", "regex", "rate_of_change", "novelty", "anomaly"]


class RuleCreate(BaseModel):
    name: str
    rule_type: RuleType
    config: dict[str, Any]
    enabled: bool = True
    cooldown_seconds: int = 900
    channel_ids: list[uuid.UUID] = []


class RuleUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None
    cooldown_seconds: int | None = None
    channel_ids: list[uuid.UUID] | None = None


class RuleOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    name: str
    rule_type: str
    config: dict[str, Any]
    enabled: bool
    cooldown_seconds: int
    last_fired_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
