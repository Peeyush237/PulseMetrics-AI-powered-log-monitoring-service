import uuid

from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentUser
from app.core.exceptions import not_found
from app.repositories.alert_repo import AlertRepository
from app.repositories.rule_repo import RuleRepository
from app.schemas.alert import AlertEventOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertEventOut])
async def list_alerts(
    user: CurrentUser,
    db: DB,
    limit: int = Query(default=50, le=200),
) -> list[AlertEventOut]:
    alert_repo = AlertRepository(db)
    events = await alert_repo.list_recent(limit=limit)
    return [AlertEventOut.model_validate(e) for e in events]


@router.get("/{alert_id}", response_model=AlertEventOut)
async def get_alert(alert_id: uuid.UUID, user: CurrentUser, db: DB) -> AlertEventOut:
    alert_repo = AlertRepository(db)
    event = await alert_repo.get(alert_id)
    if event is None:
        raise not_found("Alert not found")
    return AlertEventOut.model_validate(event)
