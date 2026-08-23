from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper

from . import crud
from .dependencies import attempt_by_id
from .shemas import AttemptCreate, AttemptRead, AttemptUpdatePartial

router = APIRouter(tags=["Attempts"])


@router.get("/", response_model=list[AttemptRead])
async def get_attempts(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_attempts(session=session)


@router.post("/", response_model=AttemptRead, status_code=status.HTTP_201_CREATED)
async def create_attempt(
    attempt_in: AttemptCreate,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.create_attempt(session=session, attempt_in=attempt_in)


@router.get("/{attempt_id}", response_model=AttemptRead)
async def get_attempt_by_id(attempt: AttemptRead = Depends(attempt_by_id)):
    return attempt


@router.patch("/{attempt_id}", response_model=AttemptRead)
async def update_attempt(
    attempt_update: AttemptUpdatePartial,
    session: AsyncSession = Depends(db_helper.session_dependency),
    attempt: AttemptRead = Depends(attempt_by_id),
):
    return await crud.update_attempt(
        session=session,
        attempt=attempt,
        attempt_update=attempt_update,
        partial=True,
    )


@router.delete("/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attempt(
    attempt: AttemptRead = Depends(attempt_by_id),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud.delete_attempt(session=session, attempt=attempt)
