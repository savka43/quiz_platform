from fastapi import APIRouter, Depends, HTTPException, Path

from api_v1.auth.dependencies import get_current_user
from core.models import User
from .shemas import UserRead

router = APIRouter(tags=["Users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user_by_id(
    user_id: int = Path(gt=0),
    user: User = Depends(get_current_user),
):
    if user_id != user.id:
        raise HTTPException(403, "Access forbidden")
    return user
