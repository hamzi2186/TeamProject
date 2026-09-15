"""Interactive real-integration smoke test for the complete Phase 1 auth flow."""
from __future__ import annotations

import getpass
import json
import os
import secrets
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(base: str, method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{path} failed with HTTP {exc.code}: {detail}") from exc


def main() -> int:
    base = input("Backend URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    email = os.getenv("TREX_SMOKE_EMAIL") or input(
        "Email address that can receive the OTP: "
    ).strip()
    password = (
        secrets.token_urlsafe(24)
        if os.getenv("TREX_SMOKE_GENERATE_PASSWORD") == "1"
        else getpass.getpass("Password (10+ characters): ")
    )
    print("Registering and requesting a real OTP through TPI/SMTP...")
    call(base, "POST", "/api/v1/auth/register", {"email": email, "password": password})
    otp = getpass.getpass("Enter the six-digit OTP received by email: ").strip()
    call(base, "POST", "/api/v1/auth/verify-email", {"email": email, "code": otp})
    session = call(base, "POST", "/api/v1/auth/login", {"email": email, "password": password})
    access = session["access_token"]
    refresh = session["refresh_token"]
    me = call(base, "GET", "/api/v1/auth/me", token=access)
    if me["email"].lower() != email.lower():
        raise RuntimeError("/auth/me returned a different identity")
    rotated = call(base, "POST", "/api/v1/auth/refresh", {"refresh_token": refresh})
    call(base, "POST", "/api/v1/auth/logout", {"refresh_token": rotated["refresh_token"]})
    print("PASS: register -> DB user -> SMTP OTP -> verify -> login -> me -> refresh -> logout")
    print("No token or OTP values were written to disk or displayed by this script.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
