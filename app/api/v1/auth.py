from fastapi import APIRouter
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, CurrentUser
from app.core.exceptions import bad_request, conflict, unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.organization import Organization
from app.db.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: DB) -> TokenResponse:
    user_repo = UserRepository(db)
    existing = await user_repo.get_by_email(body.email)
    if existing:
        raise conflict("Email already registered")

    org = Organization(name=body.org_name)
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access = create_access_token(
        str(user.id), extra={"org": str(org.id), "role": user.role}
    )
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DB) -> TokenResponse:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise unauthorized("Invalid email or password")

    access = create_access_token(
        str(user.id), extra={"org": str(user.organization_id), "role": user.role}
    )
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: DB) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise unauthorized("Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise unauthorized("Invalid or expired refresh token")

    import uuid
    from app.repositories.user_repo import UserRepository
    user_repo = UserRepository(db)
    user = await user_repo.get(uuid.UUID(user_id))
    if not user:
        raise unauthorized("User not found")

    access = create_access_token(
        str(user.id), extra={"org": str(user.organization_id), "role": user.role}
    )
    new_refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        role=user.role,
        organization_id=str(user.organization_id),
    )
