from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Question

from .shemas import QuestionCreate, QuestionUpdate, QuestionUpdatePartial


async def get_questions(session: AsyncSession) -> list[Question]:
    stmt = select(Question).order_by(Question.id)
    result = await session.execute(stmt)
    questions = result.scalars().all()
    return list(questions)


async def get_question_by_id(session: AsyncSession, id: int) -> Question | None:
    return await session.get(Question, id)


async def create_question(
    session: AsyncSession,
    question_in: QuestionCreate,
) -> Question:
    question = Question(**question_in.model_dump())
    session.add(question)
    await session.commit()
    return question


async def update_question(
    session: AsyncSession,
    question: Question,
    question_update: QuestionUpdate | QuestionUpdatePartial,
    partial: bool = False,
) -> Question:
    for name, value in question_update.model_dump(exclude_unset=partial).items():
        setattr(question, name, value)
    await session.commit()
    return question


async def delete_question(session: AsyncSession, question: Question) -> None:
    await session.delete(question)
    await session.commit()
