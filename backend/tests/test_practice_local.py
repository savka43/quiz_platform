"""Supplemental ORM/API checks on real SQLite, not a replacement for PostgreSQL.

Uses a small awaitable adapter around SQLAlchemy's synchronous Session to avoid
an additional aiosqlite dependency. PostgreSQL locking/migrations are NOT tested.
"""
import pytest
pytestmark = pytest.mark.anyio
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from core.models import Base
from test_practice_integration import (
    headers, document,
    test_full_practice_and_immutable_history as test_local_history,
    test_favorites_are_questions_and_span_tests as test_local_favorites,
    test_import_preview_does_not_save_and_confirm_validates as test_local_import,
    test_author_cannot_spoof_score_or_answer_key as test_local_score_protection,
    test_editor_rejects_foreign_question_and_rolls_back as test_local_editor,
)


class AwaitableSession:
    def __init__(self, session):
        self.session = session

    def __getattr__(self, name):
        return getattr(self.session, name)

    async def get(self, *args, **kwargs):
        return self.session.get(*args, **kwargs)

    async def execute(self, *args, **kwargs):
        return self.session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):
        return self.session.scalar(*args, **kwargs)

    async def scalars(self, *args, **kwargs):
        return self.session.scalars(*args, **kwargs)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def delete(self, obj):
        self.session.delete(obj)

    async def refresh(self, obj):
        self.session.refresh(obj)


@pytest.fixture
async def database():
    engine = create_engine('sqlite://')
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)  # Test-only database; app uses Alembic.
    with Session(engine, expire_on_commit=False) as session:
        yield AwaitableSession(session)
    engine.dispose()
