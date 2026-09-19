import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.calling import SeenWebhookEvent
from app.models.lead import Lead
from app.models.mailer import MailerBase
from app.modules.mailer.repository import MailerRepository


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(MailerBase.metadata.create_all)
        await connection.run_sync(SeenWebhookEvent.__table__.create)
        await connection.run_sync(Lead.__table__.create)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
def repo(db):
    return MailerRepository(db)
