from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import owned_attempt
from core import db_helper
from core.models import Attempt, User


async def attempt_by_id(
    attempt_id: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(db_helper.session_dependency),
    current_user: User = Depends(get_current_user),
) -> Attempt:
    return await owned_attempt(session, attempt_id, current_user)
