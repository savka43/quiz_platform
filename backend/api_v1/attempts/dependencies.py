from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper
from core.models import Attempt

from . import crud


async def attempt_by_id(
    attempt_id: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(db_helper.session_dependency),
) -> Attempt:
    attempt = await crud.get_attempt_by_id(session=session, id=attempt_id)
    if attempt is not None:
        return attempt

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Attempt {attempt_id} not found!",
    )
