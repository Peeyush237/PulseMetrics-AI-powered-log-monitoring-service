import uuid
from datetime import datetime

from pydantic import BaseModel


class ClusterOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    representative_message: str
    first_seen: datetime
    last_seen: datetime
    member_count: int
    label: str | None
    is_acknowledged: bool

    model_config = {"from_attributes": True}


class ClusterDetail(ClusterOut):
    sample_messages: list[str] = []


class ClusterUpdate(BaseModel):
    label: str | None = None
    is_acknowledged: bool | None = None
