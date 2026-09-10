"""Ownership checks shared by resource dependencies and creation routes."""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Attempt, AttemptAnswer, Question, Test, User


async def owned_test(session: AsyncSession, test_id: int, user: User) -> Test:
    test = await session.get(Test, test_id)
    if test is None:
        raise HTTPException(404, "Test not found")
    if test.user_id != user.id:
        raise HTTPException(403, "Access forbidden")
    return test


async def owned_question(session: AsyncSession, question_id: int, user: User) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise HTTPException(404, "Question not found")
    await owned_test(session, question.test_id, user)
    return question


async def owned_attempt(session: AsyncSession, attempt_id: int, user: User) -> Attempt:
    attempt = await session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(404, "Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(403, "Access forbidden")
    return attempt


async def owned_attempt_answer(session: AsyncSession, answer_id: int, user: User) -> AttemptAnswer:
    answer = await session.get(AttemptAnswer, answer_id)
    if answer is None:
        raise HTTPException(404, "Attempt answer not found")
    await owned_attempt(session, answer.attempt_id, user)
    return answer


def immutable_links(data, resource, fields: tuple[str, ...]) -> None:
    """A PATCH cannot move existing records to another parent or clear their FK."""
    for field in fields:
        if field in data.model_fields_set and getattr(data, field) != getattr(resource, field):
            raise HTTPException(409, f"Cannot change {field}")


async def answer_parent(session: AsyncSession, attempt_id: int, question_id: int, user: User) -> None:
    attempt = await owned_attempt(session, attempt_id, user)
    # Until public tests exist, answering requires access to the question's test.
    question = await owned_question(session, question_id, user)
    if question.test_id != attempt.test_id:
        raise HTTPException(422, "Question does not belong to the attempt's test")
