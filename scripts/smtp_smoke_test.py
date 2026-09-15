"""Send a real SMTP smoke email through the running TPI API without printing secrets."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    env = load_env(Path("tpi-engine/backend/.env"))
    payload = json.dumps(
        {"to": env["SMTP_FROM_EMAIL"], "template": "smtp_smoke", "variables": {}}
    ).encode()
    request = Request(
        "http://localhost:8001/api/v1/internal/email-delivery/send",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-TPI-Service-Token": env["TPI_INTERNAL_SERVICE_TOKEN"],
        },
    )
    with urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    if not result.get("accepted") or result.get("transport") != "smtp":
        raise RuntimeError("TPI did not confirm SMTP acceptance")
    print("PASS: TPI accepted and delivered a real SMTP message to the configured sender mailbox.")


if __name__ == "__main__":
    main()
