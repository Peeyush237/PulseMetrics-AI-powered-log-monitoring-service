import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    name: str
    parser_type: str = "json"
    parser_config: dict[str, Any] = {}
    retention_days: int = 30


class ApplicationUpdate(BaseModel):
    name: str | None = None
    parser_type: str | None = None
    parser_config: dict[str, Any] | None = None
    retention_days: int | None = None


class ApplicationOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    parser_type: str
    parser_config: dict[str, Any]
    retention_days: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreatedOut(ApplicationOut):
    api_key: str  # Only shown once at creation
