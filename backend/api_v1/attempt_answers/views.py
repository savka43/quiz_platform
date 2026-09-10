from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import answer_parent, immutable_links
from core import db_helper
from core.models import User

from . import crud
from .dependencies import attempt_answer_by_id
from .shemas import (
    AttemptAnswerCreate,
    AttemptAnswerRead,
    AttemptAnswerUpdatePartial,
)

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["Attempt answers"])


@router.get("/", response_model=list[AttemptAnswerRead])
async def get_attempt_answers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_attempt_answers(session=session, user_id=current_user.id)


@router.post(
    "/",
    response_model=AttemptAnswerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attempt_answer(
    attempt_answer_in: AttemptAnswerCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await answer_parent(session, attempt_answer_in.attempt_id, attempt_answer_in.question_id, current_user)
    return await crud.create_attempt_answer(
        session=session,
        attempt_answer_in=attempt_answer_in,
    )


@router.get("/{attempt_answer_id}", response_model=AttemptAnswerRead)
async def get_attempt_answer_by_id(
    attempt_answer: AttemptAnswerRead = Depends(attempt_answer_by_id),
):
    return attempt_answer


@router.patch("/{attempt_answer_id}", response_model=AttemptAnswerRead)
async def update_attempt_answer(
    attempt_answer_update: AttemptAnswerUpdatePartial,
    session: AsyncSession = Depends(db_helper.session_dependency),
    attempt_answer: AttemptAnswerRead = Depends(attempt_answer_by_id),
):
    immutable_links(attempt_answer_update, attempt_answer, ("attempt_id", "question_id"))
    return await crud.update_attempt_answer(
        session=session,
        attempt_answer=attempt_answer,
        attempt_answer_update=attempt_answer_update,
        partial=True,
    )


@router.delete(
    "/{attempt_answer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attempt_answer(
    attempt_answer: AttemptAnswerRead = Depends(attempt_answer_by_id),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud.delete_attempt_answer(
        session=session,
        attempt_answer=attempt_answer,
    )
