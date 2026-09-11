from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core import db_helper
from core.models import User, Attempt, AttemptAnswer
from api_v1.auth.dependencies import get_current_user
from api_v1.practice.schemas import AnswerInput
from api_v1.practice import service
from .dependencies import attempt_answer_by_id
from .shemas import AttemptAnswerCreate, AttemptAnswerUpdatePartial

router = APIRouter(tags=["Attempt answers"], dependencies=[Depends(get_current_user)])


@router.get("/")
async def get_attempt_answers(user: User = Depends(get_current_user),
                              session: AsyncSession = Depends(db_helper.session_dependency)):
    rows = (await session.execute(select(AttemptAnswer, Attempt.finished_at).join(Attempt)
            .where(Attempt.user_id == user.id).order_by(AttemptAnswer.id))).all()
    return [service.public_answer(answer, finished is not None) for answer, finished in rows]


@router.post("/", status_code=201)
async def create_attempt_answer(data: AttemptAnswerCreate, user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(db_helper.session_dependency)):
    # Check parent ownership before resolving the supplied question inside its snapshot.
    await service.locked_attempt(session, data.attempt_id, user)
    if data.question_id is not None:
        from api_v1.permissions import owned_question
        await owned_question(session, data.question_id, user)
    answer = await service.submit_answer(session, user, data.attempt_id,
                                        AnswerInput(**data.model_dump(exclude={'attempt_id'})))
    return service.public_answer(answer)


@router.get("/{attempt_answer_id}")
async def get_attempt_answer_by_id(answer: AttemptAnswer = Depends(attempt_answer_by_id),
                                   session: AsyncSession = Depends(db_helper.session_dependency)):
    attempt = await session.get(Attempt, answer.attempt_id)
    return service.public_answer(answer, attempt.finished_at is not None)


@router.patch("/{attempt_answer_id}")
async def update_attempt_answer(data: AttemptAnswerUpdatePartial,
                                answer: AttemptAnswer = Depends(attempt_answer_by_id),
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(db_helper.session_dependency)):
    if answer.attempt_question_id is None:
        raise HTTPException(409, "Legacy answer without a snapshot cannot be changed")
    updated = await service.submit_answer(session, user, answer.attempt_id,
        AnswerInput(attempt_question_id=answer.attempt_question_id, **data.model_dump()))
    return service.public_answer(updated)


@router.delete("/{attempt_answer_id}", status_code=204)
async def delete_attempt_answer(answer: AttemptAnswer = Depends(attempt_answer_by_id),
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(db_helper.session_dependency)):
    attempt = await service.locked_attempt(session, answer.attempt_id, user)
    service.require_open(attempt)
    await session.delete(answer)
    await session.commit()
