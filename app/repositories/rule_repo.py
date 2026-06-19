import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.rule import AlertRule, NotificationChannel, RuleChannelBinding
from app.repositories.base import BaseRepository


class RuleRepository(BaseRepository[AlertRule]):
    model = AlertRule

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_app(self, application_id: uuid.UUID) -> list[AlertRule]:
        stmt = (
            select(AlertRule)
            .where(AlertRule.application_id == application_id)
            .options(selectinload(AlertRule.channel_bindings))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_enabled(self) -> list[AlertRule]:
        stmt = (
            select(AlertRule)
            .where(AlertRule.enabled.is_(True))
            .options(selectinload(AlertRule.channel_bindings))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_last_fired(self, rule_id: uuid.UUID, fired_at: datetime) -> None:
        rule = await self.session.get(AlertRule, rule_id)
        if rule:
            rule.last_fired_at = fired_at
            await self.session.flush()

    async def bind_channel(self, rule_id: uuid.UUID, channel_id: uuid.UUID) -> None:
        binding = RuleChannelBinding(rule_id=rule_id, channel_id=channel_id)
        self.session.add(binding)
        await self.session.flush()

    async def unbind_all_channels(self, rule_id: uuid.UUID) -> None:
        stmt = select(RuleChannelBinding).where(RuleChannelBinding.rule_id == rule_id)
        result = await self.session.execute(stmt)
        for b in result.scalars().all():
            await self.session.delete(b)
        await self.session.flush()


class ChannelRepository(BaseRepository[NotificationChannel]):
    model = NotificationChannel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_org(self, organization_id: uuid.UUID) -> list[NotificationChannel]:
        stmt = select(NotificationChannel).where(
            NotificationChannel.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
