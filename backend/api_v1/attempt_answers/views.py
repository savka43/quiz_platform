from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper

from . import crud
from .dependencies import attempt_answer_by_id
from .shemas import (
    AttemptAnswerCreate,
    AttemptAnswerRead,
    AttemptAnswerUpdatePartial,
)

router = APIRouter(tags=["Attempt answers"])


@router.get("/", response_model=list[AttemptAnswerRead])
async def get_attempt_answers(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_attempt_answers(session=session)


@router.post(
    "/",
    response_model=AttemptAnswerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attempt_answer(
    attempt_answer_in: AttemptAnswerCreate,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
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
