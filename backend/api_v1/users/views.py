from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper

from . import crud
from .dependencies import user_by_id
from .shemas import UserCreate, UserRead, UserUpdatePartial

router = APIRouter(tags=["Users"])


@router.get("/", response_model=list[UserRead])
async def get_users(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_users(session=session)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.create_user(session=session, user_in=user_in)


@router.get("/{user_id}", response_model=UserRead)
async def get_user_by_id(user: UserRead = Depends(user_by_id)):
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_update: UserUpdatePartial,
    session: AsyncSession = Depends(db_helper.session_dependency),
    user: UserRead = Depends(user_by_id),
):
    return await crud.update_user(
        session=session,
        user=user,
        user_update=user_update,
        partial=True,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user: UserRead = Depends(user_by_id),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud.delete_user(session=session, user=user)
