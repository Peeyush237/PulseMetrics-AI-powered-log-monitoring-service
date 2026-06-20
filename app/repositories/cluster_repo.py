import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cluster import LogCluster
from app.repositories.base import BaseRepository


class ClusterRepository(BaseRepository[LogCluster]):
    model = LogCluster

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def find_nearest(
        self, app_id: uuid.UUID, embedding: np.ndarray, threshold: float = 0.85
    ) -> tuple[LogCluster | None, float]:
        """Return (cluster, similarity) using pgvector cosine similarity."""
        vector_str = "[" + ",".join(str(x) for x in embedding.tolist()) + "]"
        stmt = text("""
            SELECT id, 1 - (centroid <=> CAST(:vec AS vector)) AS similarity
            FROM log_clusters
            WHERE application_id = :app_id
            ORDER BY centroid <=> CAST(:vec AS vector)
            LIMIT 1
        """)
        result = await self.session.execute(
            stmt, {"app_id": str(app_id), "vec": vector_str}
        )
        row = result.fetchone()
        if row is None:
            return None, 0.0
        if row.similarity < threshold:
            return None, float(row.similarity)
        cluster = await self.session.get(LogCluster, row.id)
        return cluster, float(row.similarity)

    async def update_centroid(
        self, cluster_id: uuid.UUID, new_embedding: np.ndarray
    ) -> None:
        """Running average update of the centroid."""
        cluster = await self.session.get(LogCluster, cluster_id)
        if cluster is None:
            return
        old = np.array(cluster.centroid, dtype=np.float32)
        n = cluster.member_count
        updated = (old * n + new_embedding) / (n + 1)
        vector_str = "[" + ",".join(str(x) for x in updated.tolist()) + "]"
        stmt = text("""
            UPDATE log_clusters
            SET centroid = CAST(:vec AS vector),
                member_count = member_count + 1,
                last_seen = NOW()
            WHERE id = :id
        """)
        await self.session.execute(stmt, {"vec": vector_str, "id": str(cluster_id)})

    async def list_for_app(
        self, app_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[LogCluster]:
        stmt = (
            select(LogCluster)
            .where(LogCluster.application_id == app_id)
            .order_by(LogCluster.last_seen.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_created_after(
        self, app_id: uuid.UUID, since: datetime
    ) -> list[LogCluster]:
        stmt = select(LogCluster).where(
            LogCluster.application_id == app_id,
            LogCluster.first_seen >= since,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
