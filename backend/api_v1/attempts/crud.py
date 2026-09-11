from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Attempt

from .shemas import AttemptCreate, AttemptUpdate, AttemptUpdatePartial


async def get_attempts(session: AsyncSession, user_id: int, limit: int = 100, offset: int = 0) -> list[Attempt]:
    stmt = select(Attempt).where(Attempt.user_id == user_id).order_by(Attempt.id).limit(limit).offset(offset)
    result = await session.execute(stmt)
    attempts = result.scalars().all()
    return list(attempts)


async def get_attempt_by_id(session: AsyncSession, id: int) -> Attempt | None:
    return await session.get(Attempt, id)


async def create_attempt(
    session: AsyncSession,
    attempt_in: AttemptCreate,
    user_id: int,
) -> Attempt:
    attempt = Attempt(**attempt_in.model_dump(), user_id=user_id)
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
    # Serialize deletion with answer submission and finish on the attempt row.
    attempt = await session.scalar(select(Attempt).where(Attempt.id == attempt.id).with_for_update())
    if attempt is None:
        return
    await session.delete(attempt)
    await session.commit()
