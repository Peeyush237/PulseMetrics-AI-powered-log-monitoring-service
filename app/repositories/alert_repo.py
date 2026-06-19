import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.alert import AlertEvent
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[AlertEvent]):
    model = AlertEvent

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_rule(
        self, rule_id: uuid.UUID, limit: int = 50
    ) -> list[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .where(AlertEvent.rule_id == rule_id)
            .order_by(AlertEvent.fired_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(
        self, application_id: uuid.UUID | None = None, limit: int = 50
    ) -> list[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .order_by(AlertEvent.fired_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
