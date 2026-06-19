import asyncio
import json
import uuid
from typing import Any

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.repositories.application_repo import ApplicationRepository
from app.schemas.log import LogEntry
from app.services.ingestion import IngestionService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.tasks.ingestion_tasks.process_log_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_log_batch(self: Any, application_id: str, entries_json: list[dict]) -> dict:
    return asyncio.get_event_loop().run_until_complete(
        _process_log_batch_async(application_id, entries_json)
    )


async def _process_log_batch_async(
    application_id: str, entries_json: list[dict]
) -> dict:
    async with AsyncSessionLocal() as session:
        app_repo = ApplicationRepository(session)
        app = await app_repo.get(uuid.UUID(application_id))
        if app is None:
            logger.error("application_not_found", application_id=application_id)
            return {"error": "application not found"}

        entries = [LogEntry(**e) for e in entries_json]
        service = IngestionService(session)
        result = await service.process_batch(app, entries)
        return {"accepted": result.accepted, "rejected": len(result.rejected)}
