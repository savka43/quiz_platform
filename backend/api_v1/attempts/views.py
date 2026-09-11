from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import owned_test, immutable_links
from core import db_helper
from core.models import User
from api_v1.practice import service as practice

from . import crud
from .dependencies import attempt_by_id
from .shemas import AttemptCreate, AttemptRead, AttemptUpdatePartial

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["Attempts"])


@router.get("/", response_model=list[AttemptRead])
async def get_attempts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_attempts(session=session, user_id=current_user.id)


@router.post("/", response_model=AttemptRead, status_code=status.HTTP_201_CREATED)
async def create_attempt(
    attempt_in: AttemptCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await owned_test(session, attempt_in.test_id, current_user)
    return await practice.start_test(session, current_user, attempt_in.test_id)


@router.get("/{attempt_id}", response_model=AttemptRead)
async def get_attempt_by_id(attempt: AttemptRead = Depends(attempt_by_id)):
    return attempt


@router.patch("/{attempt_id}", response_model=AttemptRead)
async def update_attempt(
    attempt_update: AttemptUpdatePartial,
    session: AsyncSession = Depends(db_helper.session_dependency),
    attempt: AttemptRead = Depends(attempt_by_id),
):
    raise HTTPException(409, "Use the answers and finish endpoints; attempts cannot be patched")



@router.delete("/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attempt(
    attempt: AttemptRead = Depends(attempt_by_id),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud.delete_attempt(session=session, attempt=attempt)
