from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_helper
from core.models import Question

from . import crud


async def question_by_id(
    question_id: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(db_helper.session_dependency),
) -> Question:
    question = await crud.get_question_by_id(session=session, id=question_id)
    if question is not None:
        return question

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Question {question_id} not found!",
    )
