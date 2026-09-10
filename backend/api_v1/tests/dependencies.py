from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_current_user
from api_v1.permissions import owned_test
from core import db_helper
from core.models import Test, User


async def test_by_id(
    test_id: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(db_helper.session_dependency),
    current_user: User = Depends(get_current_user),
) -> Test:
    return await owned_test(session, test_id, current_user)
