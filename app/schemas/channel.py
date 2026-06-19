import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


ChannelType = Literal["email", "slack", "webhook", "console"]


class ChannelCreate(BaseModel):
    name: str
    channel_type: ChannelType
    config: dict[str, Any]


class ChannelUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None


class ChannelOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    channel_type: str
    created_at: datetime

    model_config = {"from_attributes": True}
