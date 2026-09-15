"""Verify persisted acceptance-flow state without displaying identity or token data."""
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
    query = text(
        """
        WITH latest_user AS (
            SELECT id, email_verified_at
            FROM app_users
            ORDER BY created_at DESC
            LIMIT 1
        )
        SELECT
            (SELECT email_verified_at IS NOT NULL FROM latest_user) AS verified,
            (SELECT count(*) FROM auth_credentials c JOIN latest_user u ON u.id = c.user_id)
                AS credential_count,
            (SELECT count(*) FROM auth_otp_codes o JOIN latest_user u ON u.id = o.user_id
                WHERE o.purpose = 'verify_email' AND o.used_at IS NOT NULL) AS used_otp_count,
            (SELECT count(*) FROM auth_refresh_tokens r JOIN latest_user u ON u.id = r.user_id)
                AS refresh_count,
            (SELECT count(*) FROM auth_refresh_tokens r JOIN latest_user u ON u.id = r.user_id
                WHERE r.revoked_at IS NULL) AS active_refresh_count
        """
    )
    async with engine.connect() as connection:
        row = (await connection.execute(query)).one()
    await engine.dispose()
    if not row.verified:
        raise RuntimeError("Latest acceptance user is not verified")
    if row.credential_count != 1 or row.used_otp_count < 1:
        raise RuntimeError("Credential or consumed OTP state is incomplete")
    if row.refresh_count < 2 or row.active_refresh_count != 0:
        raise RuntimeError("Refresh rotation/logout state is incomplete")
    print("PASS: verified user, credential, consumed OTP, refresh rotation, and logout persisted.")


if __name__ == "__main__":
    asyncio.run(main())
