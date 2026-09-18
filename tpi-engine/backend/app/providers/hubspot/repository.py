import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol

from sqlalchemy import DateTime, Text, select, update
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings
from app.providers.hubspot.errors import (
    HubSpotConfigurationError,
    HubSpotError,
    ProviderTemporaryError,
)


class Base(DeclarativeBase):
    pass


class HubSpotConnectionRecord(Base):
    __tablename__ = "hubspot_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hubspot_portal_id: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectionRepository(Protocol):
    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        portal_id: str,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        expires_at: datetime,
        scopes: list[str],
    ) -> HubSpotConnectionRecord: ...

    async def latest_for_user(self, user_id: uuid.UUID) -> HubSpotConnectionRecord | None: ...

    async def update_tokens(
        self,
        connection_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        expires_at: datetime,
        scopes: list[str],
    ) -> HubSpotConnectionRecord: ...

    async def set_status(
        self, connection_id: uuid.UUID, *, user_id: uuid.UUID, status: str
    ) -> None: ...


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    database_url = get_settings().database_url
    if not database_url:
        raise HubSpotConfigurationError("DATABASE_URL is required for HubSpot persistence")
    engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return async_sessionmaker(engine, expire_on_commit=False)


class SqlAlchemyConnectionRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._custom_factory = factory

    @property
    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self._custom_factory is not None:
            return self._custom_factory
        return session_factory()

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        portal_id: str,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        expires_at: datetime,
        scopes: list[str],
    ) -> HubSpotConnectionRecord:
        connection_id = uuid.uuid4()
        statement = (
            insert(HubSpotConnectionRecord)
            .values(
                id=connection_id,
                user_id=user_id,
                hubspot_portal_id=portal_id,
                encrypted_access_token=encrypted_access_token,
                encrypted_refresh_token=encrypted_refresh_token,
                expires_at=expires_at,
                scopes=scopes,
                status="connected",
            )
            .on_conflict_do_update(
                constraint="uq_hubspot_connections_user_portal",
                set_={
                    "encrypted_access_token": encrypted_access_token,
                    "encrypted_refresh_token": encrypted_refresh_token,
                    "expires_at": expires_at,
                    "scopes": scopes,
                    "status": "connected",
                    "updated_at": datetime.now(UTC),
                },
            )
            .returning(HubSpotConnectionRecord.id)
        )
        try:
            async with self._factory() as session:
                saved_id = (await session.execute(statement)).scalar_one()
                await session.commit()
                return await self._get_by_id(session, saved_id)
        except HubSpotError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            raise ProviderTemporaryError("Database operation failed") from exc

    async def latest_for_user(self, user_id: uuid.UUID) -> HubSpotConnectionRecord | None:
        try:
            async with self._factory() as session:
                return await session.scalar(
                    select(HubSpotConnectionRecord)
                    .where(HubSpotConnectionRecord.user_id == user_id)
                    .order_by(HubSpotConnectionRecord.updated_at.desc())
                    .limit(1)
                )
        except HubSpotError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            raise ProviderTemporaryError("Database operation failed") from exc

    async def update_tokens(
        self,
        connection_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        expires_at: datetime,
        scopes: list[str],
    ) -> HubSpotConnectionRecord:
        try:
            async with self._factory() as session:
                await session.execute(
                    update(HubSpotConnectionRecord)
                    .where(
                        HubSpotConnectionRecord.id == connection_id,
                        HubSpotConnectionRecord.user_id == user_id,
                    )
                    .values(
                        encrypted_access_token=encrypted_access_token,
                        encrypted_refresh_token=encrypted_refresh_token,
                        expires_at=expires_at,
                        scopes=scopes,
                        status="connected",
                        updated_at=datetime.now(UTC),
                    )
                )
                await session.commit()
                return await self._get_by_id(session, connection_id, user_id=user_id)
        except HubSpotError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            raise ProviderTemporaryError("Database operation failed") from exc

    async def set_status(
        self, connection_id: uuid.UUID, *, user_id: uuid.UUID | None = None, status: str
    ) -> None:
        try:
            async with self._factory() as session:
                stmt = update(HubSpotConnectionRecord).where(HubSpotConnectionRecord.id == connection_id)
                if user_id is not None:
                    stmt = stmt.where(HubSpotConnectionRecord.user_id == user_id)
                await session.execute(
                    stmt.values(status=status, updated_at=datetime.now(UTC))
                )
                await session.commit()
        except HubSpotError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            raise ProviderTemporaryError("Database operation failed") from exc

    async def _get_by_id(
        self, session: AsyncSession, connection_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> HubSpotConnectionRecord:
        statement = select(HubSpotConnectionRecord).where(HubSpotConnectionRecord.id == connection_id)
        if user_id is not None:
            statement = statement.where(HubSpotConnectionRecord.user_id == user_id)
        connection = await session.scalar(statement)
        if connection is None:
            raise ProviderTemporaryError("HubSpot connection persistence failed")
        return connection
