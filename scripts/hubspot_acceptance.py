"""Interactive acceptance helper for the real TPI HubSpot integration.

This script reads gitignored local configuration, but only prints the OAuth
authorization URL and provider-neutral acceptance results.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TPI_ENV = ROOT / "tpi-engine" / "backend" / ".env"
sys.path.insert(0, str(BACKEND))

from app.core.config import Settings  # noqa: E402


def tpi_token() -> str:
    value = dotenv_values(TPI_ENV).get("TPI_INTERNAL_SERVICE_TOKEN")
    if not value:
        raise RuntimeError("TPI_INTERNAL_SERVICE_TOKEN is not configured locally")
    return value


async def canonical_user_id(email: str | None) -> str:
    settings = Settings(_env_file=BACKEND / ".env")
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            if email is None:
                statement = text(
                    "SELECT id FROM app_users WHERE email_verified_at IS NOT NULL "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                result = await connection.execute(statement)
            else:
                statement = text(
                    "SELECT id FROM app_users "
                    "WHERE lower(email) = lower(:email) AND email_verified_at IS NOT NULL"
                )
                result = await connection.execute(statement, {"email": email})
            user_id = result.scalar_one_or_none()
    finally:
        await engine.dispose()
    if user_id is None:
        raise RuntimeError("No matching verified canonical user exists")
    return str(user_id)


async def persistence_summary(user_id: str) -> dict[str, object]:
    settings = Settings(_env_file=BACKEND / ".env")
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT count(*) AS row_count, "
                    "coalesce(bool_and(encrypted_access_token <> ''), false) AS access_encrypted, "
                    "coalesce(bool_and(encrypted_refresh_token <> ''), false) "
                    "AS refresh_encrypted, "
                    "coalesce(bool_and(expires_at IS NOT NULL), false) AS expiry_present, "
                    "coalesce(bool_and(jsonb_typeof(scopes) = 'array'), false) "
                    "AS scopes_normalized "
                    "FROM hubspot_connections WHERE user_id = CAST(:user_id AS uuid)"
                ),
                {"user_id": user_id},
            )
            row = result.mappings().one()
            return dict(row)
    finally:
        await engine.dispose()


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    request = Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Content-Type": "application/json",
            "X-TPI-Service-Token": token,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"TPI request failed with HTTP {exc.code}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("begin", "verify"))
    parser.add_argument("--tpi-url", default="http://localhost:8001")
    parser.add_argument(
        "--latest-verified",
        action="store_true",
        help="bind to the most recently created verified canonical user",
    )
    args = parser.parse_args()
    email = None if args.latest_verified else input("Verified canonical user email: ").strip()
    user_id = asyncio.run(canonical_user_id(email))
    token = tpi_token()

    if args.action == "begin":
        result = request_json(
            args.tpi_url,
            "POST",
            "/api/v1/internal/hubspot/connect",
            token=token,
            body={"user_id": user_id},
        )
        print("Open this one-time HubSpot authorization URL in your browser:")
        print(result["authorization_url"])
        print("After authorization and the TPI callback succeeds, run this script with 'verify'.")
        return 0

    persisted = asyncio.run(persistence_summary(user_id))
    status = request_json(
        args.tpi_url,
        "GET",
        "/api/v1/internal/hubspot/status",
        token=token,
        query={"user_id": user_id},
    )
    contacts = request_json(
        args.tpi_url,
        "GET",
        "/api/v1/internal/hubspot/contacts",
        token=token,
        query={"user_id": user_id, "limit": "1"},
    )
    allowed_contact_keys = {
        "provider_contact_id",
        "firstname",
        "lastname",
        "phone",
        "email",
        "website",
    }
    allowed_status_keys = {
        "status",
        "connected",
        "portal_id",
        "scopes",
        "created_at",
        "updated_at",
        "expires_at",
    }
    if set(status) != allowed_status_keys:
        raise RuntimeError("TPI returned a non-normalized connection-status contract")
    if not status.get("connected") or status.get("status") != "connected":
        raise RuntimeError("HubSpot connection is not connected")
    if any(set(contact) != allowed_contact_keys for contact in contacts.get("contacts", [])):
        raise RuntimeError("TPI returned a non-normalized contact contract")
    forbidden_names = {
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization",
        "properties",
        "paging",
        "results",
    }
    serialized = json.dumps({"status": status, "contacts": contacts}).lower()
    if any(name in serialized for name in forbidden_names):
        raise RuntimeError("TPI response exposed provider-specific or credential fields")
    next_after = contacts.get("next_after")
    second_page_verified = False
    if next_after:
        second_page = request_json(
            args.tpi_url,
            "GET",
            "/api/v1/internal/hubspot/contacts",
            token=token,
            query={"user_id": user_id, "limit": "1", "after": next_after},
        )
        if any(set(contact) != allowed_contact_keys for contact in second_page.get("contacts", [])):
            raise RuntimeError("TPI returned a non-normalized paginated contact contract")
        second_page_verified = True
    persistence_ok = (
        persisted["row_count"] >= 1
        and persisted["access_encrypted"]
        and persisted["refresh_encrypted"]
        and persisted["expiry_present"]
        and persisted["scopes_normalized"]
    )
    if not persistence_ok:
        raise RuntimeError("Persisted HubSpot connection metadata is incomplete")
    print(
        "Persistence: row present; encrypted credential fields populated; "
        "expiry and normalized scopes present."
    )
    print("Connection status: connected; provider-neutral status contract verified.")
    print(
        "Real contacts request: succeeded "
        f"({len(contacts.get('contacts', []))} contacts, "
        f"pagination cursor: {'present' if next_after else 'not available'})."
    )
    print(
        "Pagination: second page verified."
        if second_page_verified
        else "Pagination: supported by implementation; live account supplied no next page."
    )
    print(
        "Response contract: normalized fields only; "
        "no credentials or raw provider payload exposed."
    )
    print("No authorization codes or provider tokens were displayed or stored by this script.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
