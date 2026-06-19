import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.application import Application
from app.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):
    model = Application

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_api_key_hash(self, key_hash: str) -> Application | None:
        stmt = select(Application).where(Application.api_key_hash == key_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: uuid.UUID) -> list[Application]:
        stmt = select(Application).where(Application.organization_id == organization_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
