from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import AttemptAnswer

from .shemas import (
    AttemptAnswerCreate,
    AttemptAnswerUpdate,
    AttemptAnswerUpdatePartial,
)


async def get_attempt_answers(session: AsyncSession) -> list[AttemptAnswer]:
    stmt = select(AttemptAnswer).order_by(AttemptAnswer.id)
    result = await session.execute(stmt)
    attempt_answers = result.scalars().all()
    return list(attempt_answers)


async def get_attempt_answer_by_id(
    session: AsyncSession,
    id: int,
) -> AttemptAnswer | None:
    return await session.get(AttemptAnswer, id)


async def create_attempt_answer(
    session: AsyncSession,
    attempt_answer_in: AttemptAnswerCreate,
) -> AttemptAnswer:
    attempt_answer = AttemptAnswer(**attempt_answer_in.model_dump())
    session.add(attempt_answer)
    await session.commit()
    return attempt_answer


async def update_attempt_answer(
    session: AsyncSession,
    attempt_answer: AttemptAnswer,
    attempt_answer_update: AttemptAnswerUpdate | AttemptAnswerUpdatePartial,
    partial: bool = False,
) -> AttemptAnswer:
    for name, value in attempt_answer_update.model_dump(
        exclude_unset=partial
    ).items():
        setattr(attempt_answer, name, value)
    await session.commit()
    return attempt_answer


async def delete_attempt_answer(
    session: AsyncSession,
    attempt_answer: AttemptAnswer,
) -> None:
    await session.delete(attempt_answer)
    await session.commit()
