import base64
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, cast, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.log import Log
from app.repositories.base import BaseRepository
from app.schemas.log import SearchFilters, SearchResponse, LogOut

LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


class LogRepository(BaseRepository[Log]):
    model = Log

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def bulk_insert(self, logs: list[Log]) -> None:
        self.session.add_all(logs)
        await self.session.flush()

    async def search(
        self,
        application_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
        filters: SearchFilters,
        cluster_id: uuid.UUID | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> SearchResponse:
        stmt = (
            select(Log)
            .where(
                Log.application_id == application_id,
                Log.timestamp >= from_dt,
                Log.timestamp <= to_dt,
            )
            .order_by(Log.timestamp.desc())
        )

        stmt = self._apply_filters(stmt, filters)

        if cluster_id:
            stmt = stmt.where(Log.cluster_id == cluster_id)

        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
                stmt = stmt.where(
                    Log.timestamp < datetime.fromisoformat(cursor_data["ts"])
                )
            except Exception:
                pass

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = stmt.limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            cursor_payload = json.dumps({"ts": last.timestamp.isoformat()})
            next_cursor = base64.b64encode(cursor_payload.encode()).decode()

        return SearchResponse(
            results=[LogOut.model_validate(r) for r in rows],
            total=total,
            next_cursor=next_cursor,
        )

    def _apply_filters(self, stmt: Select, filters: SearchFilters) -> Select:
        if filters.level:
            stmt = self._apply_level_filter(stmt, filters.level)
        if filters.service:
            stmt = stmt.where(Log.service.in_(filters.service))
        if filters.message_contains:
            stmt = stmt.where(
                Log.message.op("@@")(func.to_tsquery("english", filters.message_contains))
            )
        if filters.metadata:
            for key, value in filters.metadata.items():
                stmt = stmt.where(
                    cast(Log.metadata_, JSONB)[key].astext == str(value)
                )
        return stmt

    def _apply_level_filter(self, stmt: Select, level_filter: str) -> Select:
        levels = list(LEVEL_ORDER.keys())
        if level_filter.startswith(">="):
            target = level_filter[2:].upper()
            min_order = LEVEL_ORDER.get(target, 0)
            valid = [l for l in levels if LEVEL_ORDER[l] >= min_order]
            return stmt.where(Log.level.in_(valid))
        elif level_filter.startswith("=="):
            target = level_filter[2:].upper()
            return stmt.where(Log.level == target)
        return stmt.where(Log.level == level_filter.upper())

    async def get_with_context(
        self, application_id: uuid.UUID, log_id: int, context_size: int = 10
    ) -> tuple[Log | None, list[Log], list[Log]]:
        stmt = select(Log).where(
            Log.application_id == application_id, Log.id == log_id
        )
        result = await self.session.execute(stmt)
        log = result.scalar_one_or_none()
        if not log:
            return None, [], []

        before_stmt = (
            select(Log)
            .where(
                Log.application_id == application_id,
                Log.timestamp < log.timestamp,
            )
            .order_by(Log.timestamp.desc())
            .limit(context_size)
        )
        before_result = await self.session.execute(before_stmt)
        before = list(reversed(list(before_result.scalars().all())))

        after_stmt = (
            select(Log)
            .where(
                Log.application_id == application_id,
                Log.timestamp > log.timestamp,
            )
            .order_by(Log.timestamp.asc())
            .limit(context_size)
        )
        after_result = await self.session.execute(after_stmt)
        after = list(after_result.scalars().all())

        return log, before, after

    async def count_matching(
        self,
        application_id: uuid.UUID,
        filters: SearchFilters,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        stmt = select(func.count()).where(
            Log.application_id == application_id,
            Log.timestamp >= window_start,
            Log.timestamp <= window_end,
        )
        stmt = self._apply_count_filters(stmt, filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    def _apply_count_filters(self, stmt: Any, filters: SearchFilters) -> Any:
        if filters.level:
            levels = list(LEVEL_ORDER.keys())
            if filters.level.startswith(">="):
                target = filters.level[2:].upper()
                min_order = LEVEL_ORDER.get(target, 0)
                valid = [l for l in levels if LEVEL_ORDER[l] >= min_order]
                stmt = stmt.where(Log.level.in_(valid))
        if filters.service:
            stmt = stmt.where(Log.service.in_(filters.service))
        return stmt

    async def sample_matching(
        self,
        application_id: uuid.UUID,
        filters: SearchFilters,
        window_start: datetime,
        window_end: datetime,
        limit: int = 5,
    ) -> list[Log]:
        stmt = (
            select(Log)
            .where(
                Log.application_id == application_id,
                Log.timestamp >= window_start,
                Log.timestamp <= window_end,
            )
            .order_by(Log.timestamp.desc())
            .limit(limit)
        )
        stmt = self._apply_count_filters(stmt, filters)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_hourly_counts(
        self,
        application_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT
                date_trunc('hour', timestamp) AS hour,
                level,
                COUNT(*) AS count
            FROM logs
            WHERE application_id = :app_id
              AND timestamp BETWEEN :from_dt AND :to_dt
            GROUP BY hour, level
            ORDER BY hour
        """)
        result = await self.session.execute(
            stmt, {"app_id": str(application_id), "from_dt": from_dt, "to_dt": to_dt}
        )
        return [{"hour": r.hour, "level": r.level, "count": r.count} for r in result]

    async def get_top_errors(
        self,
        application_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT message, COUNT(*) AS count
            FROM logs
            WHERE application_id = :app_id
              AND timestamp BETWEEN :from_dt AND :to_dt
              AND level IN ('ERROR', 'CRITICAL')
            GROUP BY message
            ORDER BY count DESC
            LIMIT :limit
        """)
        result = await self.session.execute(
            stmt,
            {"app_id": str(application_id), "from_dt": from_dt, "to_dt": to_dt, "limit": limit},
        )
        return [{"message": r.message, "count": r.count} for r in result]
