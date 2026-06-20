import uuid

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.exceptions import conflict, not_found
from app.core.security import generate_api_key
from app.db.models.application import Application
from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationCreatedOut,
    ApplicationOut,
    ApplicationUpdate,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
async def list_applications(user: CurrentUser, db: DB) -> list[ApplicationOut]:
    repo = ApplicationRepository(db)
    apps = await repo.list_for_org(user.organization_id)
    return [ApplicationOut.model_validate(a) for a in apps]


@router.post("", response_model=ApplicationCreatedOut, status_code=201)
async def create_application(
    body: ApplicationCreate, user: CurrentUser, db: DB
) -> ApplicationCreatedOut:
    repo = ApplicationRepository(db)
    existing = await repo.list_for_org(user.organization_id)
    if any(a.name == body.name for a in existing):
        raise conflict(f"Application '{body.name}' already exists")

    raw_key, key_hash = generate_api_key()
    app = Application(
        organization_id=user.organization_id,
        name=body.name,
        api_key_hash=key_hash,
        parser_type=body.parser_type,
        parser_config=body.parser_config,
        retention_days=body.retention_days,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)

    # api_key is not a column on the model — fold the persisted fields in and add
    # the freshly generated raw key (shown only once, at creation).
    return ApplicationCreatedOut(
        **ApplicationOut.model_validate(app).model_dump(),
        api_key=raw_key,
    )


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(app_id: uuid.UUID, user: CurrentUser, db: DB) -> ApplicationOut:
    repo = ApplicationRepository(db)
    app = await repo.get(app_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")
    return ApplicationOut.model_validate(app)


@router.patch("/{app_id}", response_model=ApplicationOut)
async def update_application(
    app_id: uuid.UUID, body: ApplicationUpdate, user: CurrentUser, db: DB
) -> ApplicationOut:
    repo = ApplicationRepository(db)
    app = await repo.get(app_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    if body.name is not None:
        app.name = body.name
    if body.parser_type is not None:
        app.parser_type = body.parser_type
    if body.parser_config is not None:
        app.parser_config = body.parser_config
    if body.retention_days is not None:
        app.retention_days = body.retention_days

    await db.commit()
    await db.refresh(app)
    return ApplicationOut.model_validate(app)


@router.delete("/{app_id}", status_code=204)
async def delete_application(app_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    repo = ApplicationRepository(db)
    app = await repo.get(app_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")
    await repo.delete(app)
    await db.commit()


@router.post("/{app_id}/rotate-key", response_model=dict)
async def rotate_api_key(app_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    repo = ApplicationRepository(db)
    app = await repo.get(app_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    raw_key, key_hash = generate_api_key()
    app.api_key_hash = key_hash
    await db.commit()
    return {"api_key": raw_key, "message": "Store this key securely — it will not be shown again"}
