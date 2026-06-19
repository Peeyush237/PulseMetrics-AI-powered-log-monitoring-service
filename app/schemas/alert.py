import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AlertEventOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    fired_at: datetime
    resolved_at: datetime | None
    severity: str
    payload: dict[str, Any]
    sample_log_ids: list[int] | None

    model_config = {"from_attributes": True}
