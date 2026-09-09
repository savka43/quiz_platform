from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
import pytest
from sqlalchemy import func, select

from api_v1.auth.utils import decode_jwt, encode_jwt, validate_password
from core import settings
from core.models import RefreshSession, User

pytestmark = pytest.mark.anyio
PREFIX = "/api/v1"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def registered_login(client, registration):
    response = await client.post(f"{PREFIX}/auth/register", json=registration)
    assert response.status_code == 201, response.text
    response = await client.post(f"{PREFIX}/auth/login", data={
        "username": registration["email"], "password": registration["password"],
    })
    assert response.status_code == 200, response.text
    return response.json()


async def test_registration_persists_bcrypt_and_login(client, database, registration):
    tokens = await registered_login(client, registration)
    user = await database.scalar(select(User).where(User.email == registration["email"]))
    assert user.active
    assert user.hashed_password.startswith("$2b$")
    assert validate_password(registration["password"], user.hashed_password)
    assert tokens["token_type"] == "bearer"
    for kind in ("access", "refresh"):
        payload = decode_jwt(tokens[f"{kind}_token"])
        assert payload["sub"] == str(user.id)
        assert payload["type"] == kind
        assert payload["exp"] > payload["iat"]
        assert "hashed_password" not in payload
    response = await client.get(f"{PREFIX}/users/me", headers=bearer(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == registration["email"]
    assert "hashed_password" not in response.json()
    assert await database.scalar(select(func.count()).select_from(RefreshSession).where(
        RefreshSession.user_id == user.id)) == 1


async def test_duplicate_email_case_insensitive(client, registration):
    assert (await client.post(f"{PREFIX}/auth/register", json=registration)).status_code == 201
    registration["email"] = registration["email"].upper()
    assert (await client.post(f"{PREFIX}/auth/register", json=registration)).status_code == 409
    response = await client.post(f"{PREFIX}/auth/login", data={
        "username": registration["email"], "password": registration["password"],
    })
    assert response.status_code == 200


@pytest.mark.parametrize("change", [
    {"email": "not-email"}, {"password": "short"}, {"password": "x" * 73}, {"password": "я" * 37},
    {"hashed_password": "fake"}, {"active": False}, {"user_id": 99},
])
async def test_registration_validation(client, registration, change):
    registration.update(change)
    assert (await client.post(f"{PREFIX}/auth/register", json=registration)).status_code == 422


async def test_bad_credentials(client, registration):
    await registered_login(client, registration)
    for email, password in [
        (registration["email"], "wrong"), ("missing@example.com", registration["password"]),
    ]:
        response = await client.post(f"{PREFIX}/auth/login", data={"username": email, "password": password})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


async def test_access_and_refresh_are_not_interchangeable(client, registration):
    tokens = await registered_login(client, registration)
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(tokens["refresh_token"]))).status_code == 401
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["access_token"]))).status_code == 401
    assert (await client.post(f"{PREFIX}/auth/logout", headers=bearer(tokens["access_token"]))).status_code == 401


async def test_refresh_rotation_and_logout(client, database, registration):
    tokens = await registered_login(client, registration)
    response = await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))
    assert response.status_code == 200, response.text
    newer = response.json()
    assert newer["refresh_token"] != tokens["refresh_token"]
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(newer["access_token"]))).status_code == 200
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))).status_code == 401
    response = await client.post(f"{PREFIX}/auth/logout", headers=bearer(newer["refresh_token"]))
    assert response.status_code == 204
    assert response.content == b""
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(newer["refresh_token"]))).status_code == 401
    # Access tokens deliberately remain valid until exp; logout revokes refresh only.
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(newer["access_token"]))).status_code == 200


@pytest.mark.parametrize("path,method", [
    ("/users/me", "get"), ("/auth/refresh", "post"), ("/auth/logout", "post"),
])
async def test_missing_or_malformed_tokens(client, path, method):
    request = getattr(client, method)
    for headers in ({}, bearer("not-a-jwt")):
        assert (await request(f"{PREFIX}{path}", headers=headers)).status_code == 401


@pytest.mark.parametrize("kind,path,method", [
    ("access", "/users/me", "get"), ("refresh", "/auth/refresh", "post"),
])
async def test_expired_tokens(client, registration, kind, path, method):
    tokens = await registered_login(client, registration)
    sub = decode_jwt(tokens["access_token"])["sub"]
    expired = encode_jwt({"sub": sub, "type": kind}, expire_timedelta=timedelta(seconds=-1))
    assert (await getattr(client, method)(f"{PREFIX}{path}", headers=bearer(expired))).status_code == 401


@pytest.mark.parametrize("claim,value", [("sub", "abc"), ("sub", "9" * 100), ("sub", 1), ("type", "other"), ("jti", None), ("exp", None)])
async def test_invalid_claims(client, registration, claim, value):
    tokens = await registered_login(client, registration)
    payload = decode_jwt(tokens["access_token"])
    if value is None:
        payload.pop(claim)
    else:
        payload[claim] = value
    token = jwt.encode(payload, settings.auth_jwt.private_key_path.read_text(), algorithm=settings.auth_jwt.algorithm)
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(token))).status_code == 401


async def test_wrong_signature(client, registration):
    from cryptography.hazmat.primitives.asymmetric import rsa
    tokens = await registered_login(client, registration)
    token = jwt.encode(decode_jwt(tokens["access_token"]), rsa.generate_private_key(public_exponent=65537, key_size=2048), algorithm="RS256")
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(token))).status_code == 401


async def test_inactive_user_denied_everywhere(client, database, registration):
    tokens = await registered_login(client, registration)
    user = await database.get(User, int(decode_jwt(tokens["access_token"])["sub"]))
    user.active = False
    await database.commit()
    assert (await client.post(f"{PREFIX}/auth/login", data={"username": user.email, "password": registration["password"]})).status_code == 403
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(tokens["access_token"]))).status_code == 403
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))).status_code == 403


async def test_deleted_user_denied(client, database, registration):
    tokens = await registered_login(client, registration)
    user = await database.get(User, int(decode_jwt(tokens["access_token"])["sub"]))
    await database.delete(user)
    await database.commit()
    assert (await client.get(f"{PREFIX}/users/me", headers=bearer(tokens["access_token"]))).status_code == 401
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))).status_code == 401


async def test_refresh_requires_database_session(client, database, registration):
    tokens = await registered_login(client, registration)
    sub = decode_jwt(tokens["access_token"])["sub"]
    unregistered = encode_jwt({"sub": sub, "type": "refresh"})
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(unregistered))).status_code == 401
    record = await database.scalar(select(RefreshSession).where(RefreshSession.jti == decode_jwt(tokens["refresh_token"])["jti"]))
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await database.commit()
    assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))).status_code == 401


async def test_user_endpoints_cannot_change_hash_or_read_other_user(client, registration):
    tokens = await registered_login(client, registration)
    user_id = int(decode_jwt(tokens["access_token"])["sub"])
    headers = bearer(tokens["access_token"])
    assert (await client.get(f"{PREFIX}/users/{user_id}", headers=headers)).status_code == 200
    assert (await client.get(f"{PREFIX}/users/{user_id + 1}", headers=headers)).status_code == 403
    assert (await client.patch(f"{PREFIX}/users/{user_id}", headers=headers, json={"hashed_password": "fake"})).status_code == 405
    assert (await client.post(f"{PREFIX}/users/", json={"email": "evil@example.com", "hashed_password": "fake"})).status_code in (404, 405)


@pytest.mark.parametrize("legacy", [True, False])
async def test_legacy_and_invalid_hashes(client, database, registration, legacy):
    hashed = bcrypt.hashpw(registration["password"].encode(), bcrypt.gensalt()).decode() if legacy else "old-invalid-hash"
    user = User(email=registration["email"], hashed_password=hashed, active=True)
    database.add(user)
    await database.commit()
    response = await client.post(f"{PREFIX}/auth/login", data={"username": user.email, "password": registration["password"]})
    assert response.status_code == (200 if legacy else 401)
    if legacy:
        await database.refresh(user)
        assert user.hashed_password == hashed


async def test_swagger_oauth_and_demo_removed(client):
    schema = (await client.get("/openapi.json")).json()
    assert schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == f"{PREFIX}/auth/login"
    assert not any("demo-auth" in path for path in schema["paths"])


async def test_concurrent_refresh_and_failed_rotation_rollback(registration, monkeypatch):
    """Use independent committed connections, as in separate API requests/workers."""
    import asyncio
    import os

    from fastapi import HTTPException
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from api_v1.auth import service
    from core import db_helper
    from main import app

    engine = create_async_engine(os.environ.get("TEST_DATABASE_URL", settings.database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def independent_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[db_helper.session_dependency] = independent_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await registered_login(client, registration)
            original = service.issue_tokens

            async def failed_issue(*args, **kwargs):
                raise HTTPException(503, "Simulated failure before commit")

            monkeypatch.setattr(service, "issue_tokens", failed_issue)
            assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))).status_code == 503
            monkeypatch.setattr(service, "issue_tokens", original)
            # Failed rotation must not consume the old token. Two requests race for it.
            responses = await asyncio.gather(*[
                client.post(f"{PREFIX}/auth/refresh", headers=bearer(tokens["refresh_token"]))
                for _ in range(2)
            ])
            assert sorted(response.status_code for response in responses) == [200, 401]
            rotated = next(response.json() for response in responses if response.status_code == 200)
            assert (await client.post(f"{PREFIX}/auth/logout", headers=bearer(rotated["refresh_token"]))).status_code == 204
            # A fresh connection also sees the committed revocation.
            assert (await client.post(f"{PREFIX}/auth/refresh", headers=bearer(rotated["refresh_token"]))).status_code == 401
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(User).where(User.email == registration["email"]))
            await session.commit()
        await engine.dispose()


@pytest.mark.parametrize("password", ["a" * 72, "я" * 36])
async def test_bcrypt_password_byte_boundary(client, registration, password):
    registration["password"] = password
    await registered_login(client, registration)
    response = await client.post(f"{PREFIX}/auth/login", data={
        "username": registration["email"], "password": password + "a",
    })
    assert response.status_code == 401
