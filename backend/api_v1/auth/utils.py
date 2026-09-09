from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from core.config import settings

password_hash = PasswordHash.recommended()
# Equal-cost verification for an unknown email.
DUMMY_PASSWORD_HASH = password_hash.hash("dummy-password-never-used-for-login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def validate_password(password: str, hashed_pwd: str) -> bool:
    try:
        if hashed_pwd.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(password.encode(), hashed_pwd.encode())
        return password_hash.verify(password, hashed_pwd)
    except (ValueError, TypeError, UnknownHashError):
        return False


def encode_jwt(payload: dict, *, expire_timedelta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    data = payload.copy()
    data.update(
        iat=now,
        exp=now + (expire_timedelta if expire_timedelta is not None else timedelta(
            minutes=settings.auth_jwt.access_token_expire_minutes
        )),
        jti=uuid4().hex,
    )
    return jwt.encode(
        data, settings.auth_jwt.private_key_path.read_text(),
        algorithm=settings.auth_jwt.algorithm,
    )


def decode_jwt(token: str) -> dict:
    return jwt.decode(
        token, settings.auth_jwt.public_key_path.read_text(),
        algorithms=[settings.auth_jwt.algorithm],
        options={"require": ["sub", "exp", "iat", "jti", "type"]},
    )
