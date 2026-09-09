from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper, settings
from core.models import User
from .utils import decode_jwt

access_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")
refresh_scheme = HTTPBearer(auto_error=False, scheme_name="RefreshToken")


def unauthorized() -> HTTPException:
    return HTTPException(401, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"})


def token_payload(token: str, expected_type: str) -> dict:
    try:
        payload = decode_jwt(token)
        sub = payload["sub"]
        jti = payload["jti"]
        if (payload["type"] != expected_type or not isinstance(sub, str)
                or not sub.isascii() or not sub.isdecimal()
                or not 0 < int(sub) <= 2147483647
                or not isinstance(jti, str) or len(jti) != 32):
            raise unauthorized()
        return payload
    except (InvalidTokenError, ValueError, TypeError, KeyError, OverflowError):
        raise unauthorized() from None


async def user_from_payload(payload: dict, session: AsyncSession) -> User:
    user = await session.get(User, int(payload["sub"]))
    if user is None:
        raise unauthorized()
    if not user.active:
        raise HTTPException(403, "User inactive")
    return user


async def get_current_user(
    token: str = Depends(access_scheme),
    session: AsyncSession = Depends(db_helper.session_dependency),
) -> User:
    return await user_from_payload(token_payload(token, "access"), session)


def get_refresh_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(refresh_scheme),
) -> dict:
    if credentials is None:
        raise unauthorized()
    return token_payload(credentials.credentials, "refresh")
