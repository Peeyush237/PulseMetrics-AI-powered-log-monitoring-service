import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import DB, CurrentUser
from app.core.exceptions import not_found
from app.repositories.application_repo import ApplicationRepository
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _parse_range(
    from_dt: datetime | None, to_dt: datetime | None
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    to = to_dt or now
    from_ = from_dt or (now - timedelta(hours=24))
    return from_, to


@router.get("/timeline.png")
async def timeline_chart(
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
) -> Response:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    from_, to = _parse_range(from_dt, to_dt)
    svc = AnalyticsService(db)
    png_bytes = await svc.timeline_png(application_id, from_, to)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/top-errors.png")
async def top_errors_chart(
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
) -> Response:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    from_, to = _parse_range(from_dt, to_dt)
    svc = AnalyticsService(db)
    png_bytes = await svc.top_errors_png(application_id, from_, to)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/summary")
async def summary(
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
) -> dict:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    from_, to = _parse_range(from_dt, to_dt)
    svc = AnalyticsService(db)
    return await svc.summary(application_id, from_, to)
