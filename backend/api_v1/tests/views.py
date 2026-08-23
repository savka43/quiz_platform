from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper

from . import crud
from .dependencies import test_by_id
from .shemas import TestCreate, TestRead, TestUpdatePartial

router = APIRouter(tags=["Tests"])


@router.get("/", response_model=list[TestRead])
async def get_tests(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.get_tests(session=session)


@router.post("/", response_model=TestRead, status_code=status.HTTP_201_CREATED)
async def create_test(
    test_in: TestCreate,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud.create_test(session=session, test_in=test_in)


@router.get("/{test_id}/", response_model=TestRead)
async def get_test_by_id(test: TestRead = Depends(test_by_id)):
    return test


@router.patch("/{test_id}/", response_model=TestRead)
async def update_test(
    test_update: TestUpdatePartial,
    session: AsyncSession = Depends(db_helper.session_dependency),
    test: TestRead = Depends(test_by_id),
):
    return await crud.update_test(
        session=session,
        test=test,
        test_update=test_update,
        partial=True,
    )


@router.delete("/{test_id}/")
async def delete_test(
    test: TestRead = Depends(test_by_id),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud.delete_test(session=session, test=test)
