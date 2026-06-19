import uuid

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.exceptions import not_found
from app.db.models.rule import AlertRule
from app.repositories.application_repo import ApplicationRepository
from app.repositories.rule_repo import RuleRepository
from app.schemas.rule import RuleCreate, RuleOut, RuleUpdate

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
async def list_rules(application_id: uuid.UUID, user: CurrentUser, db: DB) -> list[RuleOut]:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    rule_repo = RuleRepository(db)
    rules = await rule_repo.list_for_app(application_id)
    return [RuleOut.model_validate(r) for r in rules]


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(
    application_id: uuid.UUID, body: RuleCreate, user: CurrentUser, db: DB
) -> RuleOut:
    app_repo = ApplicationRepository(db)
    app = await app_repo.get(application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Application not found")

    rule = AlertRule(
        application_id=application_id,
        name=body.name,
        rule_type=body.rule_type,
        config=body.config,
        enabled=body.enabled,
        cooldown_seconds=body.cooldown_seconds,
        created_by=user.id,
    )
    db.add(rule)
    await db.flush()

    rule_repo = RuleRepository(db)
    for ch_id in body.channel_ids:
        await rule_repo.bind_channel(rule.id, ch_id)

    await db.commit()
    await db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(rule_id: uuid.UUID, user: CurrentUser, db: DB) -> RuleOut:
    rule_repo = RuleRepository(db)
    rule = await rule_repo.get(rule_id)
    if rule is None:
        raise not_found("Rule not found")

    app_repo = ApplicationRepository(db)
    app = await app_repo.get(rule.application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Rule not found")

    return RuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: uuid.UUID, body: RuleUpdate, user: CurrentUser, db: DB
) -> RuleOut:
    rule_repo = RuleRepository(db)
    rule = await rule_repo.get(rule_id)
    if rule is None:
        raise not_found("Rule not found")

    app_repo = ApplicationRepository(db)
    app = await app_repo.get(rule.application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.config is not None:
        rule.config = body.config
    if body.enabled is not None:
        rule.enabled = body.enabled
    if body.cooldown_seconds is not None:
        rule.cooldown_seconds = body.cooldown_seconds
    if body.channel_ids is not None:
        await rule_repo.unbind_all_channels(rule.id)
        for ch_id in body.channel_ids:
            await rule_repo.bind_channel(rule.id, ch_id)

    await db.commit()
    await db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    rule_repo = RuleRepository(db)
    rule = await rule_repo.get(rule_id)
    if rule is None:
        raise not_found("Rule not found")

    app_repo = ApplicationRepository(db)
    app = await app_repo.get(rule.application_id)
    if not app or app.organization_id != user.organization_id:
        raise not_found("Rule not found")

    await rule_repo.delete(rule)
    await db.commit()
