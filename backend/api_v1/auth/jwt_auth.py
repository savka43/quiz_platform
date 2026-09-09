from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.users.shemas import UserRead
from core import db_helper

from . import service
from .dependencies import get_refresh_payload, user_from_payload
from .schemas import RegisterRequest, TokenInfo

router = APIRouter(tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await service.register(data, session)


@router.post("/login", response_model=TokenInfo)
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    # OAuth2 calls this field username; our user identity is an email address.
    user = await service.authenticate(form.username, form.password, session)
    response.headers["Cache-Control"] = "no-store"
    return await service.issue_tokens(user, session)


@router.post("/refresh", response_model=TokenInfo)
async def refresh(
    response: Response,
    payload: dict = Depends(get_refresh_payload),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await user_from_payload(payload, session)
    await service.consume_refresh(payload, session)
    response.headers["Cache-Control"] = "no-store"
    return await service.issue_tokens(user, session)


@router.post("/logout", status_code=204)
async def logout(
    payload: dict = Depends(get_refresh_payload),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await service.consume_refresh(payload, session)
    await session.commit()
