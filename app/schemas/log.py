import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    timestamp: datetime | None = None
    level: str = "INFO"
    service: str | None = None
    message: str
    metadata: dict[str, Any] = {}


class IngestRequest(BaseModel):
    entries: list[LogEntry] = Field(..., max_length=1000)


class IngestResponse(BaseModel):
    accepted: int
    rejected: list[dict[str, Any]] = []


class LogOut(BaseModel):
    id: int
    application_id: uuid.UUID
    timestamp: datetime
    level: str
    service: str | None
    message: str
    metadata: dict[str, Any]
    cluster_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class LogWithContext(LogOut):
    context_before: list[LogOut] = []
    context_after: list[LogOut] = []


class SearchFilters(BaseModel):
    level: str | None = None          # ">=ERROR", "==INFO", etc.
    service: list[str] | None = None
    message_contains: str | None = None
    metadata: dict[str, Any] | None = None


class SearchRequest(BaseModel):
    application_id: uuid.UUID
    from_: datetime = Field(..., alias="from")
    to: datetime
    filters: SearchFilters = SearchFilters()
    cluster_id: uuid.UUID | None = None
    limit: int = Field(default=100, le=1000)
    cursor: str | None = None

    model_config = {"populate_by_name": True}


class SearchResponse(BaseModel):
    results: list[LogOut]
    total: int
    next_cursor: str | None
