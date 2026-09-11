import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1 import router as api_v1_router
from api_v1.imports.service import MAX_BYTES
from core import db_helper, settings
from core.upload_limit import UploadLimitMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check key configuration at startup, without logging the keys or tokens.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    private = serialization.load_pem_private_key(settings.auth_jwt.private_key_path.read_bytes(), password=None)
    public = serialization.load_pem_public_key(settings.auth_jwt.public_key_path.read_bytes())
    if not isinstance(private, rsa.RSAPrivateKey) or not isinstance(public, rsa.RSAPublicKey):
        raise RuntimeError('JWT requires RSA keys')
    if private.public_key().public_numbers() != public.public_numbers():
        raise RuntimeError('JWT public/private keys do not match')
    logger.info('Quiz API started')
    try:
        yield
    finally:
        await db_helper.engine.dispose()
        logger.info('Quiz API stopped')


app = FastAPI(title='Quiz Test API', version='1.0.0', lifespan=lifespan)
app.add_middleware(UploadLimitMiddleware, prefix=f'{settings.api_prefix}/import/', max_bytes=MAX_BYTES + 65536)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type'])
app.include_router(router=api_v1_router, prefix=settings.api_prefix)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    logger.error('Database integrity conflict: method=%s path=%s', request.method, request.url.path)
    return JSONResponse({'detail': 'Data conflict; refresh the resource and try again'}, status_code=409)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error('Database operation failed: method=%s path=%s error=%s', request.method, request.url.path, type(exc).__name__)
    return JSONResponse({'detail': 'Database operation failed'}, status_code=503)


@app.get('/')
async def hello():
    return {'name': 'Quiz Test API', 'docs': '/docs'}


@app.get('/health', tags=['Health'])
async def health(session: AsyncSession = Depends(db_helper.session_dependency)):
    await session.execute(text('SELECT 1'))
    return {'status': 'ok'}
