from fastapi import HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from core.models import Test, Question, AnswerOption, User
from api_v1.permissions import owned_test
from .schemas import TestDocument, QuestionInput


async def test_questions(session: AsyncSession, test_id: int) -> list[Question]:
    result = await session.scalars(select(Question).where(Question.test_id == test_id)
        .options(selectinload(Question.options)).order_by(Question.position, Question.id))
    return list(result)


def question_document(q: Question, *, option_ids: bool = False) -> dict:
    return {
        'id': q.id, 'text': q.text, 'question_type': q.question_type,
        'correct_answer': q.correct_answer, 'blanks': q.blanks,
        'explanation': q.explanation,
        'options': [dict(text=o.text, is_correct=o.is_correct,
                         **({'id': o.id} if option_ids else {}))
                    for o in sorted(q.options, key=lambda o: (o.position, o.id or 0))],
    }


async def apply_question(session: AsyncSession, q: Question, data: QuestionInput, position: int):
    q.text = data.text
    q.question_type = data.question_type
    q.correct_answer = data.correct_answer
    q.blanks = [b.model_dump() for b in data.blanks]
    q.explanation = data.explanation
    q.position = position
    # Flush deletes before inserting replacement positions (unique per question).
    q.options = []
    await session.flush()
    q.options = [AnswerOption(text=o.text, is_correct=o.is_correct, position=i)
                 for i, o in enumerate(data.options)]


async def save_document(session: AsyncSession, user: User, data: TestDocument,
                        test_id: int | None = None, source: str = 'manual') -> Test:
    if test_id is None:
        if any(q.id is not None for q in data.questions):
            raise HTTPException(422, 'New tests cannot reference existing question IDs')
        test = Test(title=data.title, description=data.description, user_id=user.id, source=source)
        session.add(test)
        await session.flush()
        existing = {}
    else:
        test = await owned_test(session, test_id, user)
        await session.execute(select(Test.id).where(Test.id == test_id).with_for_update())
        existing = {q.id: q for q in await test_questions(session, test_id)}
        if any(q.id is not None and q.id not in existing for q in data.questions):
            raise HTTPException(403, 'Question does not belong to this test')
    test.title, test.description = data.title, data.description
    test.updated_at = func.now()
    keep = {q.id for q in data.questions if q.id is not None}
    for qid, question in existing.items():
        if qid not in keep:
            await session.delete(question)
    for i, item in enumerate(data.questions):
        question = existing.get(item.id)
        if question is None:
            question = Question(test_id=test.id, text=item.text, correct_answer='', options=[])
            session.add(question)
        await apply_question(session, question, item, i)
    await session.commit()
    await session.refresh(test)
    return test


async def read_document(session: AsyncSession, user: User, test_id: int) -> dict:
    test = await owned_test(session, test_id, user)
    questions = await test_questions(session, test_id)
    return dict(id=test.id, title=test.title, description=test.description, source=test.source,
                questions=[question_document(q) for q in questions])
