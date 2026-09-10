from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import owned_attempt_answer
from core import db_helper
from core.models import AttemptAnswer, User


async def attempt_answer_by_id(
    attempt_answer_id: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(db_helper.session_dependency),
    current_user: User = Depends(get_current_user),
) -> AttemptAnswer:
    return await owned_attempt_answer(session, attempt_answer_id, current_user)
