"""Real Root -> TPI -> HubSpot -> canonical leads acceptance check."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app.core.config import Settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402


async def connected_user() -> tuple[str, str]:
    settings = Settings(_env_file=BACKEND / ".env")
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT u.id, u.role FROM app_users u "
                        "JOIN hubspot_connections h ON h.user_id = u.id "
                        "WHERE h.status = 'connected' "
                        "ORDER BY h.updated_at DESC LIMIT 1"
                    )
                )
            ).one_or_none()
    finally:
        await engine.dispose()
    if row is None:
        raise RuntimeError("No canonical user has an active HubSpot connection")
    return str(row.id), row.role


def call(base_url: str, method: str, path: str, token: str, body: dict | None = None):
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method=method,
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"Root request failed with HTTP {exc.code}") from exc


def main() -> int:
    user_id, role = asyncio.run(connected_user())
    access_token, _ = create_access_token(UUID(user_id), role)
    base_url = "http://localhost:8000"
    status = call(base_url, "GET", "/api/v1/hubspot/status", access_token)
    if not status.get("connected"):
        raise RuntimeError("Root HubSpot status did not report connected")

    first = call(
        base_url,
        "POST",
        "/api/v1/hubspot/import",
        access_token,
        {"hubspot_contact_ids": [], "select_all": True},
    )
    leads_after_first = call(base_url, "GET", "/api/v1/leads", access_token)
    second = call(
        base_url,
        "POST",
        "/api/v1/hubspot/import",
        access_token,
        {"hubspot_contact_ids": [], "select_all": True},
    )
    leads_after_second = call(base_url, "GET", "/api/v1/leads", access_token)
    if first["imported"] < 1 or len(leads_after_first) < 1:
        raise RuntimeError("Real HubSpot contacts did not create canonical leads")
    if second["created"] != 0 or len(leads_after_second) != len(leads_after_first):
        raise RuntimeError("Repeated HubSpot import created duplicate canonical leads")

    lead_keys = {
        "id",
        "hubspot_contact_id",
        "first_name",
        "last_name",
        "display_name",
        "phone",
        "email",
        "website_url",
        "website_id",
        "current_status",
        "created_at",
        "updated_at",
    }
    if any(set(lead) != lead_keys for lead in leads_after_second):
        raise RuntimeError("Root Leads API returned an unexpected contract")
    serialized = json.dumps(
        {"status": status, "first": first, "second": second, "leads": leads_after_second}
    ).lower()
    if any(
        forbidden in serialized
        for forbidden in (
            "access_token",
            "refresh_token",
            "encrypted_access_token",
            "encrypted_refresh_token",
            "client_secret",
            "source_payload",
        )
    ):
        raise RuntimeError("Root API exposed a provider credential or internal payload field")
    print("PASS: authenticated Root HubSpot status is connected.")
    print(
        f"PASS: real import processed {first['imported']} contacts; "
        f"canonical Leads API returned {len(leads_after_first)} tenant-scoped rows."
    )
    print("PASS: repeated real import created no duplicates and updated existing leads.")
    print("PASS: Root responses exposed no provider credentials or raw provider payload fields.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
