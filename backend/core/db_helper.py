from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import async_sessionmaker


class DataBaseHelper:
    def __init__(self, url: str):
        self.engine = create_async_engine(url=url, echo=False, hide_parameters=True)
        self.session_factory = async_sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, autocommit=False
        )

    async def session_dependency(self):
        async with self.session_factory() as session:
            yield session
