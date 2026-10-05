"""Async engine / session factory. Re-initialisable so tests can target another DB."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


class DatabaseState:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]

    def __init__(self) -> None:
        self.init(settings.database_url, null_pool=settings.db_null_pool)

    def init(self, url: str, *, null_pool: bool = False) -> None:
        kwargs: dict[str, object] = {"pool_pre_ping": True}
        if null_pool:
            kwargs["poolclass"] = NullPool
        else:
            kwargs.update(pool_size=10, max_overflow=20)
        self.engine = create_async_engine(url, **kwargs)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()


db = DatabaseState()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request; commit is explicit in services."""
    async with db.sessionmaker() as session:
        yield session
