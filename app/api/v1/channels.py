import uuid

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.exceptions import not_found
from app.db.models.rule import NotificationChannel
from app.repositories.rule_repo import ChannelRepository
from app.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelOut])
async def list_channels(user: CurrentUser, db: DB) -> list[ChannelOut]:
    repo = ChannelRepository(db)
    channels = await repo.list_for_org(user.organization_id)
    return [ChannelOut.model_validate(c) for c in channels]


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(body: ChannelCreate, user: CurrentUser, db: DB) -> ChannelOut:
    channel = NotificationChannel(
        organization_id=user.organization_id,
        name=body.name,
        channel_type=body.channel_type,
        config=body.config,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return ChannelOut.model_validate(channel)


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel(channel_id: uuid.UUID, user: CurrentUser, db: DB) -> ChannelOut:
    repo = ChannelRepository(db)
    channel = await repo.get(channel_id)
    if not channel or channel.organization_id != user.organization_id:
        raise not_found("Channel not found")
    return ChannelOut.model_validate(channel)


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: uuid.UUID, body: ChannelUpdate, user: CurrentUser, db: DB
) -> ChannelOut:
    repo = ChannelRepository(db)
    channel = await repo.get(channel_id)
    if not channel or channel.organization_id != user.organization_id:
        raise not_found("Channel not found")

    if body.name is not None:
        channel.name = body.name
    if body.config is not None:
        channel.config = body.config

    await db.commit()
    await db.refresh(channel)
    return ChannelOut.model_validate(channel)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(channel_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    repo = ChannelRepository(db)
    channel = await repo.get(channel_id)
    if not channel or channel.organization_id != user.organization_id:
        raise not_found("Channel not found")
    await repo.delete(channel)
    await db.commit()
