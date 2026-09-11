"""Apply the entire migration chain to an isolated PostgreSQL database."""
import asyncio
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from core import settings

pytestmark = pytest.mark.anyio


async def test_empty_database_upgrade_and_legacy_history():
    name = 'quiz_migration_' + uuid4().hex
    params = dict(host=settings.postgres_host, port=settings.postgres_port,
                  user=settings.postgres_user, password=settings.postgres_password)
    admin = await asyncpg.connect(**params, database=settings.postgres_db)
    await admin.execute(f'CREATE DATABASE "{name}"')
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, 'POSTGRES_DB': name, 'POSTGRES_HOST': settings.postgres_host,
           'POSTGRES_PORT': str(settings.postgres_port), 'POSTGRES_USER': settings.postgres_user,
           'POSTGRES_PASSWORD': settings.postgres_password}

    async def alembic(*args):
        completed = await asyncio.to_thread(subprocess.run,
            [str(backend / '.venv/bin/alembic'), *args], cwd=backend, env=env,
            text=True, capture_output=True, timeout=60)
        assert completed.returncode == 0, completed.stderr

    try:
        await alembic('upgrade', '044028594a61')
        conn = await asyncpg.connect(**params, database=name)
        try:
            uid = await conn.fetchval("INSERT INTO users(email,hashed_password,active) VALUES('migration@example.com','unused',true) RETURNING id")
            tid = await conn.fetchval("INSERT INTO tests(title,user_id) VALUES('Legacy',$1) RETURNING id", uid)
            qid = await conn.fetchval("INSERT INTO questions(test_id,text,correct_answer) VALUES($1,'Q','A') RETURNING id", tid)
            aid = await conn.fetchval("INSERT INTO attempts(user_id,test_id,finished_at) VALUES($1,$2,now()) RETURNING id", uid, tid)
            await conn.execute("INSERT INTO attempt_answers(attempt_id,question_id,user_answer,is_correct) VALUES($1,$2,'A',true)", aid, qid)
        finally:
            await conn.close()
        await alembic('upgrade', 'head')
        await alembic('check')
        conn = await asyncpg.connect(**params, database=name)
        try:
            assert await conn.fetchval('SELECT count(*) FROM users') == 1
            assert await conn.fetchval('SELECT score FROM attempts WHERE id=$1', aid) == 100
            snapshot = await conn.fetchrow('SELECT id,payload FROM attempt_questions WHERE attempt_id=$1', aid)
            assert json.loads(snapshot['payload'])['correct_answer'] == 'A'
            assert await conn.fetchval('SELECT attempt_question_id FROM attempt_answers WHERE attempt_id=$1', aid) == snapshot['id']
            await conn.execute('DELETE FROM tests WHERE id=$1', tid)
            assert await conn.fetchval('SELECT test_id FROM attempts WHERE id=$1', aid) is None
            assert json.loads(await conn.fetchval('SELECT payload FROM attempt_questions WHERE id=$1', snapshot['id']))['text'] == 'Q'
        finally:
            await conn.close()
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
