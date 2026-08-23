from fastapi import FastAPI

from api_v1 import router as api_v1_router
from core import settings

app = FastAPI()

app.include_router(router=api_v1_router, prefix=settings.api_prefix)


@app.get("/")
async def hello():
    return {"hello": "hello world"}
