"""Integration tests use PostgreSQL, rolling back all records after each test."""
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core import db_helper, settings
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def database():
    # Override with a separate migrated database when available.
    engine = create_async_engine(
        os.environ.get("TEST_DATABASE_URL", settings.database_url),
        poolclass=NullPool, hide_parameters=True,
    )
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(database):
    async def session_override():
        yield database
    app.dependency_overrides[db_helper.session_dependency] = session_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def registration():
    return {"email": f"auth-test-{uuid4().hex}@example.com", "password": "Valid-test-password-43"}
