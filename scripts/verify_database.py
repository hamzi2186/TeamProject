"""Verify real database connectivity and Phase 1 table presence without exposing its URL."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402, I001


async def main() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    expected = {"app_users", "auth_credentials", "auth_otp_codes", "auth_refresh_tokens"}
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = ANY(:names)"
            ),
            {"names": list(expected)},
        )
        found = {row[0] for row in result}
        await connection.execute(text("SELECT 1"))
    await engine.dispose()
    missing = expected - found
    if missing:
        raise RuntimeError(f"Missing Phase 1 tables: {', '.join(sorted(missing))}")
    print("PASS: real PostgreSQL connectivity and all four Phase 1 auth tables verified.")


if __name__ == "__main__":
    asyncio.run(main())
