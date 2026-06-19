import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.application import Application
from app.db.models.log import Log
from app.parsers.base import ParsedLog
from app.parsers.factory import ParserFactory
from app.repositories.cluster_repo import ClusterRepository
from app.repositories.log_repo import LogRepository
from app.schemas.log import IngestResponse, LogEntry
from app.services.clustering import ClusteringService

logger = get_logger(__name__)


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.log_repo = LogRepository(session)
        self.cluster_repo = ClusterRepository(session)
        self.clustering = ClusteringService(self.cluster_repo)

    async def process_batch(
        self, application: Application, entries: list[LogEntry]
    ) -> IngestResponse:
        parser = ParserFactory.from_application(application)
        logs: list[Log] = []
        rejected: list[dict[str, Any]] = []

        for i, entry in enumerate(entries):
            try:
                if entry.message:
                    parsed = ParsedLog(
                        timestamp=entry.timestamp or datetime.now(timezone.utc),
                        level=entry.level.upper(),
                        service=entry.service,
                        message=entry.message,
                        metadata=entry.metadata,
                    )
                else:
                    continue

                cluster_id, is_new = await self.clustering.assign(
                    application.id, parsed.message
                )

                log = Log(
                    application_id=application.id,
                    timestamp=parsed.timestamp,
                    level=parsed.level,
                    service=parsed.service,
                    message=parsed.message,
                    metadata_=parsed.metadata,
                    raw=parsed.raw,
                    cluster_id=cluster_id,
                )
                logs.append(log)

            except Exception as exc:
                logger.warning("log_parse_failed", index=i, error=str(exc))
                rejected.append({"index": i, "error": str(exc)})

        if logs:
            await self.log_repo.bulk_insert(logs)
            await self.session.commit()

        return IngestResponse(accepted=len(logs), rejected=rejected)

    async def process_raw_batch(
        self, application: Application, raw_lines: list[str]
    ) -> IngestResponse:
        parser = ParserFactory.from_application(application)
        entries: list[LogEntry] = []
        rejected: list[dict[str, Any]] = []

        for i, raw in enumerate(raw_lines):
            try:
                parsed = parser.parse(raw)
                entries.append(
                    LogEntry(
                        timestamp=parsed.timestamp,
                        level=parsed.level,
                        service=parsed.service,
                        message=parsed.message,
                        metadata=parsed.metadata,
                    )
                )
            except Exception as exc:
                rejected.append({"index": i, "error": str(exc)})

        result = await self.process_batch(application, entries)
        result.rejected.extend(rejected)
        return result
