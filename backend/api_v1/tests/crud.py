from sqlalchemy import select
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import session

from core.models import Test

from .shemas import TestCreate, TestRead, TestUpdate, TestUpdatePartial


async def get_tests(session: AsyncSession) -> list[Test]:
    stmt = select(Test).order_by(Test.id)
    result = await session.execute(stmt)
    tests = result.scalars().all()
    return list(tests)


async def get_test_by_id(session: AsyncSession, id: int) -> Test | None:
    return await session.get(Test, id)


async def create_test(session: AsyncSession, test_in: TestCreate) -> Test:
    test = Test(**test_in.model_dump())
    session.add(test)
    await session.commit()
    return test


async def update_test(
    session: AsyncSession,
    test: Test,
    test_update: TestUpdate | TestUpdatePartial,
    partial: bool = False,
) -> Test:
    for name, value in test_update.model_dump():
        setattr(test, name, value)
    await session.commit()
    return test


async def delete_test(session: AsyncSession, test: Test) -> None:
    await session.delete(test)
    await session.commit()
