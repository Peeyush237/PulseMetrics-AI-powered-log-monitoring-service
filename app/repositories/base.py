from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: UUID) -> ModelT | None:
        result = await self.session.get(self.model, id)
        return result

    async def list(self, **filters: Any) -> list[ModelT]:
        stmt = select(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()
