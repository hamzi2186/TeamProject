import os
import sys
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

is_worker = (
    os.getenv("IS_CELERY_WORKER", "").lower() in {"1", "true", "yes"}
    or "celery" in sys.argv[0].lower()
    or any("celery" in arg.lower() for arg in sys.argv)
)

if is_worker:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
else:
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
    )

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
