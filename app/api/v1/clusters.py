import uuid

from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentUser
from app.core.exceptions import not_found
from app.repositories.application_repo import ApplicationRepository
from app.repositories.cluster_repo import ClusterRepository
from app.schemas.cluster import ClusterDetail, ClusterOut, ClusterUpdate

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterOut])
async def list_clusters(
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> list[ClusterOut]:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    cluster_repo = ClusterRepository(db)
    clusters = await cluster_repo.list_for_app(application_id, limit=limit, offset=offset)
    return [ClusterOut.model_validate(c) for c in clusters]


@router.get("/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(cluster_id: uuid.UUID, user: CurrentUser, db: DB) -> ClusterDetail:
    cluster_repo = ClusterRepository(db)
    cluster = await cluster_repo.get(cluster_id)
    if cluster is None:
        raise not_found("Cluster not found")

    # Verify org ownership
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(cluster.application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Cluster not found")

    from sqlalchemy import select, text
    from app.db.models.log import Log
    stmt = (
        select(Log.message)
        .where(Log.cluster_id == cluster_id)
        .order_by(Log.timestamp.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    samples = [r[0] for r in result.fetchall()]

    detail = ClusterDetail.model_validate(cluster)
    detail.sample_messages = samples
    return detail


@router.patch("/{cluster_id}", response_model=ClusterOut)
async def update_cluster(
    cluster_id: uuid.UUID, body: ClusterUpdate, user: CurrentUser, db: DB
) -> ClusterOut:
    cluster_repo = ClusterRepository(db)
    cluster = await cluster_repo.get(cluster_id)
    if cluster is None:
        raise not_found("Cluster not found")

    app_repo = ApplicationRepository(db)
    app = await app_repo.get(cluster.application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Cluster not found")

    if body.label is not None:
        cluster.label = body.label
    if body.is_acknowledged is not None:
        cluster.is_acknowledged = body.is_acknowledged

    await db.commit()
    await db.refresh(cluster)
    return ClusterOut.model_validate(cluster)
