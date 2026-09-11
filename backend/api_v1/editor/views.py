from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core import db_helper
from core.models import User
from api_v1.auth.dependencies import get_current_user
from .schemas import TestDocument
from .service import save_document, read_document

router = APIRouter(tags=['Test editor'])


@router.post('/tests/document', status_code=201)
async def create_document(data: TestDocument, user: User = Depends(get_current_user),
                          session: AsyncSession = Depends(db_helper.session_dependency)):
    test = await save_document(session, user, data)
    return await read_document(session, user, test.id)


@router.get('/tests/{test_id}/editor')
async def get_editor(test_id: int, user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(db_helper.session_dependency)):
    return await read_document(session, user, test_id)


@router.put('/tests/{test_id}/editor')
async def put_editor(test_id: int, data: TestDocument, user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(db_helper.session_dependency)):
    await save_document(session, user, data, test_id)
    return await read_document(session, user, test_id)
