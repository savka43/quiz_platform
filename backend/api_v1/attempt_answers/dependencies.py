from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper
from core.models import AttemptAnswer

from . import crud


async def attempt_answer_by_id(
    attempt_answer_id: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(db_helper.session_dependency),
) -> AttemptAnswer:
    attempt_answer = await crud.get_attempt_answer_by_id(
        session=session,
        id=attempt_answer_id,
    )
    if attempt_answer is not None:
        return attempt_answer

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Attempt answer {attempt_answer_id} not found!",
    )
