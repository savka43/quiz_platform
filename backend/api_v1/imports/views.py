import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from api_v1.auth.dependencies import get_current_user
from api_v1.editor.schemas import TestDocument
from api_v1.editor.service import save_document, read_document
from core import db_helper
from core.models import User
from .service import MAX_BYTES, extract_pdf, parse_pdf_text, parse_html, parse_json_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/import', tags=['Import'])


@router.post('/{format}/preview')
async def preview(format: Literal['pdf', 'html', 'json'], file: UploadFile = File(),
                  user: User = Depends(get_current_user)):
    suffix = Path(file.filename or '').suffix.casefold()
    suffixes = {'pdf': {'.pdf'}, 'html': {'.html', '.htm'}, 'json': {'.json'}}
    if suffix not in suffixes[format]:
        raise HTTPException(415, 'File extension does not match the import format')
    allowed = {
        'pdf': {'application/pdf', 'application/octet-stream'},
        'html': {'text/html', 'application/xhtml+xml', 'application/octet-stream'},
        'json': {'application/json', 'text/plain', 'application/octet-stream'},
    }[format]
    if file.content_type not in allowed:
        raise HTTPException(415, 'Unsupported file content type')
    try:
        data = await file.read(MAX_BYTES + 1)
    finally:
        await file.close()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Maximum file size is 8 MiB')
    title = Path(file.filename or 'Импорт').stem[:200]
    try:
        if format == 'pdf':
            text = await run_in_threadpool(extract_pdf, data)
            result = await run_in_threadpool(parse_pdf_text, text, title)
        elif format == 'html':
            result = await run_in_threadpool(parse_html, data.decode('utf-8-sig'), title)
        else:
            result = await run_in_threadpool(parse_json_text, data.decode('utf-8-sig'), title)
    except (ValueError, UnicodeError) as exc:
        logger.info('Import rejected: user=%s format=%s', user.id, format)
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    logger.info('Import preview: user=%s format=%s questions=%s', user.id, format, len(result.questions))
    return result.response()


@router.post('/{format}/confirm', status_code=201)
async def confirm(format: Literal['pdf', 'html', 'json'], data: TestDocument,
                  user: User = Depends(get_current_user),
                  session: AsyncSession = Depends(db_helper.session_dependency)):
    # Client submits edited content, not a trusted parser result or arbitrary ORM IDs.
    test = await save_document(session, user, data, source=f'{format}_import')
    logger.info('Import saved: user=%s test=%s', user.id, test.id)
    return await read_document(session, user, test.id)
