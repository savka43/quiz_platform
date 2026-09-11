from sqlalchemy import select, func
from fastapi import HTTPException
from pydantic import ValidationError
from api_v1.editor.service import apply_question, question_document
from api_v1.editor.schemas import QuestionInput
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Question, Test

from .shemas import QuestionCreate, QuestionUpdate, QuestionUpdatePartial


async def get_questions(session: AsyncSession, user_id: int) -> list[Question]:
    stmt = select(Question).join(Test, Question.test_id == Test.id).where(Test.user_id == user_id).order_by(Question.id)
    result = await session.execute(stmt)
    questions = result.scalars().all()
    return list(questions)


async def get_question_by_id(session: AsyncSession, id: int) -> Question | None:
    return await session.get(Question, id)


async def create_question(
    session: AsyncSession,
    question_in: QuestionCreate,
) -> Question:
    if question_in.id is not None:
        raise HTTPException(422, "Cannot supply a question ID on create")
    question = Question(test_id=question_in.test_id, text=question_in.text, correct_answer="", options=[])
    session.add(question)
    position = (await session.scalar(select(func.max(Question.position)).where(Question.test_id == question_in.test_id)))
    await apply_question(session, question, QuestionInput(**question_in.model_dump(exclude={'test_id'})), (position + 1) if position is not None else 0)
    await session.commit()
    return question


async def update_question(
    session: AsyncSession,
    question: Question,
    question_update: QuestionUpdate | QuestionUpdatePartial,
    partial: bool = False,
) -> Question:
    fields = question_update.model_dump(exclude_unset=partial, exclude={'test_id'})
    try:
        data = QuestionInput(**{**question_document(question), **fields})
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from None
    await apply_question(session, question, data, question.position)
    await session.commit()
    return question


async def delete_question(session: AsyncSession, question: Question) -> None:
    await session.delete(question)
    await session.commit()
