from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import owned_test, immutable_links
from core import db_helper
from core.models import User

from . import crud
from .dependencies import question_by_id
from .shemas import QuestionCreate, QuestionRead, QuestionUpdatePartial

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["Questions"])


@router.get("/", response_model=list[QuestionRead])
async def get_questions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_questions(session=session, user_id=current_user.id)


@router.post(
    "/",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(
    question_in: QuestionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await owned_test(session, question_in.test_id, current_user)
    return await crud.create_question(session=session, question_in=question_in)


@router.get("/{question_id}", response_model=QuestionRead)
async def get_question_by_id(
    question: QuestionRead = Depends(question_by_id),
):
    return question


@router.patch("/{question_id}", response_model=QuestionRead)
async def update_question(
    question_update: QuestionUpdatePartial,
    session: AsyncSession = Depends(db_helper.session_dependency),
    question: QuestionRead = Depends(question_by_id),
):
    immutable_links(question_update, question, ("test_id",))
    return await crud.update_question(
        session=session,
        question=question,
        question_update=question_update,
        partial=True,
    )


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question: QuestionRead = Depends(question_by_id),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud.delete_question(session=session, question=question)
