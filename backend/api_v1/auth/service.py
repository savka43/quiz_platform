from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from core import settings
from core.models import RefreshSession, User

from .dependencies import unauthorized
from .schemas import RegisterRequest, TokenInfo
from .utils import (
    DUMMY_PASSWORD_HASH,
    decode_jwt,
    encode_jwt,
    hash_password,
    validate_password,
)


async def register(data: RegisterRequest, session: AsyncSession) -> User:
    existing = await session.scalar(
        select(User.id).where(func.lower(User.email) == data.email)
    )
    if existing is not None:
        raise HTTPException(409, "Email already registered")
    hashed = await run_in_threadpool(hash_password, data.password)
    user = User(email=str(data.email), hashed_password=hashed, active=True)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Email already registered") from None
    return user


async def authenticate(email: str, password: str, session: AsyncSession) -> User:
    if len(email) > 255 or not 1 <= len(password.encode("utf-8")) <= 72:
        raise unauthorized()
    user = await session.scalar(
        select(User).where(func.lower(User.email) == email.strip().lower())
    )
    valid = await run_in_threadpool(
        validate_password,
        password,
        user.hashed_password if user else DUMMY_PASSWORD_HASH,
    )
    if user is None or not valid:
        raise unauthorized()
    if not user.active:
        raise HTTPException(403, "User inactive")
    return user


async def issue_tokens(user: User, session: AsyncSession) -> TokenInfo:
    access = encode_jwt({"sub": str(user.id), "type": "access"})
    refresh = encode_jwt(
        {"sub": str(user.id), "type": "refresh"},
        expire_timedelta=timedelta(days=settings.auth_jwt.refresh_token_expire_days),
    )
    payload = decode_jwt(refresh)
    session.add(
        RefreshSession(
            user_id=user.id,
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
        )
    )
    await session.commit()
    return TokenInfo(access_token=access, refresh_token=refresh)


async def consume_refresh(payload: dict, session: AsyncSession) -> None:
    # Atomic UPDATE makes a refresh token single-use, including concurrent requests.
    now = datetime.now(timezone.utc)
    result = await session.execute(
        update(RefreshSession)
        .where(
            RefreshSession.jti == payload["jti"],
            RefreshSession.user_id == int(payload["sub"]),
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        )
        .values(revoked_at=now)
        .returning(RefreshSession.id)
    )
    if result.scalar_one_or_none() is None:
        raise unauthorized()
