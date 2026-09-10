from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Test

from .shemas import TestCreate, TestUpdate, TestUpdatePartial


async def get_tests(session: AsyncSession, user_id: int) -> list[Test]:
    stmt = select(Test).where(Test.user_id == user_id).order_by(Test.id)
    result = await session.execute(stmt)
    tests = result.scalars().all()
    return list(tests)


async def get_test_by_id(session: AsyncSession, id: int) -> Test | None:
    return await session.get(Test, id)


async def create_test(session: AsyncSession, test_in: TestCreate, user_id: int) -> Test:
    test = Test(**test_in.model_dump(), user_id=user_id)
    session.add(test)
    await session.commit()
    return test


async def update_test(
    session: AsyncSession,
    test: Test,
    test_update: TestUpdate | TestUpdatePartial,
    partial: bool = False,
) -> Test:
    for name, value in test_update.model_dump(exclude_unset=partial).items():
        setattr(test, name, value)
    await session.commit()
    return test


async def delete_test(session: AsyncSession, test: Test) -> None:
    await session.delete(test)
    await session.commit()
