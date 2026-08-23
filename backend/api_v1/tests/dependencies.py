from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper
from core.models import Test

from . import crud


async def test_by_id(
    test_id: Annotated[int, Path()],
    session: AsyncSession = Depends(db_helper.session_dependency),
) -> Test:
    test = await crud.get_test_by_id(session=session, id=test_id)
    if test is not None:
        return test

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Test {test_id} not found!",
    )
