from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Attempt

from .shemas import AttemptCreate, AttemptUpdate, AttemptUpdatePartial


async def get_attempts(session: AsyncSession) -> list[Attempt]:
    stmt = select(Attempt).order_by(Attempt.id)
    result = await session.execute(stmt)
    attempts = result.scalars().all()
    return list(attempts)


async def get_attempt_by_id(session: AsyncSession, id: int) -> Attempt | None:
    return await session.get(Attempt, id)


async def create_attempt(
    session: AsyncSession,
    attempt_in: AttemptCreate,
) -> Attempt:
    attempt = Attempt(**attempt_in.model_dump())
    session.add(attempt)
    await session.commit()
    return attempt


async def update_attempt(
    session: AsyncSession,
    attempt: Attempt,
    attempt_update: AttemptUpdate | AttemptUpdatePartial,
    partial: bool = False,
) -> Attempt:
    for name, value in attempt_update.model_dump(exclude_unset=partial).items():
        setattr(attempt, name, value)
    await session.commit()
    return attempt


async def delete_attempt(session: AsyncSession, attempt: Attempt) -> None:
    await session.delete(attempt)
    await session.commit()
