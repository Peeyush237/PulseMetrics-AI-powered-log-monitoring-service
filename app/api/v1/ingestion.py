from fastapi import APIRouter

from app.api.deps import AppFromApiKey, DB
from app.schemas.log import IngestRequest, IngestResponse
from app.services.ingestion import IngestionService
from app.tasks.ingestion_tasks import process_log_batch

router = APIRouter(prefix="/logs", tags=["ingestion"])


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_logs(
    body: IngestRequest,
    app: AppFromApiKey,
    db: DB,
) -> IngestResponse:
    entries_json = [e.model_dump(mode="json") for e in body.entries]
    process_log_batch.delay(str(app.id), entries_json)
    return IngestResponse(accepted=len(body.entries))
