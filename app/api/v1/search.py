import uuid

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.exceptions import not_found
from app.repositories.application_repo import ApplicationRepository
from app.repositories.log_repo import LogRepository
from app.schemas.log import LogOut, LogWithContext, SearchRequest, SearchResponse

router = APIRouter(prefix="/logs", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_logs(body: SearchRequest, user: CurrentUser, db: DB) -> SearchResponse:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(body.application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    log_repo = LogRepository(db)
    return await log_repo.search(
        application_id=body.application_id,
        from_dt=body.from_,
        to_dt=body.to,
        filters=body.filters,
        cluster_id=body.cluster_id,
        limit=body.limit,
        cursor=body.cursor,
    )


@router.get("/{log_id}", response_model=LogWithContext)
async def get_log(
    log_id: int,
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
) -> LogWithContext:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    log_repo = LogRepository(db)
    log, before, after = await log_repo.get_with_context(application_id, log_id)
    if log is None:
        raise not_found("Log not found")

    return LogWithContext(
        **LogOut.model_validate(log).model_dump(),
        context_before=[LogOut.model_validate(l) for l in before],
        context_after=[LogOut.model_validate(l) for l in after],
    )
