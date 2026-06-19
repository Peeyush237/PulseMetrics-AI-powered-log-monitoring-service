import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import unauthorized
from app.core.security import decode_token, hash_api_key
from app.db.models.application import Application
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.application_repo import ApplicationRepository
from app.repositories.user_repo import UserRepository

bearer = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise unauthorized("Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise unauthorized()
    except JWTError:
        raise unauthorized("Invalid or expired token")

    user_repo = UserRepository(session)
    user = await user_repo.get(uuid.UUID(user_id))
    if user is None:
        raise unauthorized("User not found")
    return user


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


async def get_app_from_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> Application:
    if not x_api_key:
        raise unauthorized("Missing X-Api-Key header")
    key_hash = hash_api_key(x_api_key)
    app_repo = ApplicationRepository(session)
    app = await app_repo.get_by_api_key_hash(key_hash)
    if app is None:
        raise unauthorized("Invalid API key")
    return app


# Type aliases for clean endpoint signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DB = Annotated[AsyncSession, Depends(get_db)]
AppFromApiKey = Annotated[Application, Depends(get_app_from_api_key)]
