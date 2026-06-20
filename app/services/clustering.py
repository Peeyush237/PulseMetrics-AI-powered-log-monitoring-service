import re
import uuid

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.cluster import LogCluster
from app.repositories.cluster_repo import ClusterRepository
from app.services.embeddings import embed

logger = get_logger(__name__)

_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_NUM_RE = re.compile(r"\b\d+(\.\d+)?\b")
_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*\b")


class ClusteringService:
    SIMILARITY_THRESHOLD = settings.clustering_threshold

    def __init__(self, cluster_repo: ClusterRepository) -> None:
        self.cluster_repo = cluster_repo

    async def assign(
        self, app_id: uuid.UUID, message: str
    ) -> tuple[uuid.UUID, bool]:
        """Return (cluster_id, is_new). is_new=True means a novel cluster was created."""
        normalized = self._normalize(message)
        embedding = self._embed(normalized)

        nearest, similarity = await self.cluster_repo.find_nearest(
            app_id, embedding, threshold=self.SIMILARITY_THRESHOLD
        )

        if nearest is not None:
            await self.cluster_repo.update_centroid(nearest.id, embedding)
            return nearest.id, False

        vector_list = embedding.tolist()
        new_cluster = LogCluster(
            application_id=app_id,
            centroid=vector_list,
            representative_message=message,
        )
        saved = await self.cluster_repo.save(new_cluster)
        logger.info("new_cluster_created", cluster_id=str(saved.id), message=message[:100])
        return saved.id, True

    def _embed(self, text: str) -> np.ndarray:
        return embed(text)

    @staticmethod
    def _normalize(message: str) -> str:
        msg = _TS_RE.sub("<TIMESTAMP>", message)
        msg = _UUID_RE.sub("<UUID>", msg)
        msg = _NUM_RE.sub("<NUM>", msg)
        return msg.lower()
