from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt

from core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


# Equal-cost verification for an unknown email.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-never-used-for-login")


def validate_password(password: str, hashed_pwd: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_pwd.encode("ascii"))
    except ValueError, TypeError, UnicodeError:
        return False


def encode_jwt(payload: dict, *, expire_timedelta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    data = payload.copy()
    data.update(
        iat=now,
        exp=now
        + (
            expire_timedelta
            if expire_timedelta is not None
            else timedelta(minutes=settings.auth_jwt.access_token_expire_minutes)
        ),
        jti=uuid4().hex,
    )
    return jwt.encode(
        data,
        settings.auth_jwt.private_key_path.read_text(),
        algorithm=settings.auth_jwt.algorithm,
    )


def decode_jwt(token: str) -> dict:
    return jwt.decode(
        token,
        settings.auth_jwt.public_key_path.read_text(),
        algorithms=[settings.auth_jwt.algorithm],
        options={"require": ["sub", "exp", "iat", "jti", "type"]},
    )
