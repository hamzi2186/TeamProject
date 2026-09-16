#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "http://localhost:8002"
FIXTURE = Path(__file__).parents[1] / "fixtures" / "demo_campaign.json"


def post_conversation(payload: dict, user_id: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{API_BASE}/api/v1/sms/conversations",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Demo-User-Id": user_id,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    campaign = fixture["campaign"]
    sender = fixture["sender"]
    failed = False
    for lead in fixture["leads"]:
        template = campaign["message_template"].replace(
            "{{first_name}}", lead["first_name"]
        )
        status, result = post_conversation(
            {
                "campaign_id": campaign["id"],
                "lead_id": lead["id"],
                "contact_name": lead["full_name"],
                "from_number": sender["from_number"],
                "to_number": lead["phone_number"],
                "timezone": lead["timezone"],
                "message_template": template,
                "campaign_objective": campaign["objective"],
                "knowledge_context": campaign["knowledge_context"],
                "consent_source": lead["consent_source"],
                "consented": lead["sms_consent"],
                "max_agent_turns": campaign["max_agent_turns"],
            },
            sender["user_id"],
        )
        if status == 201:
            print(f"created {lead['full_name']}: {result['id']}")
        elif status == 409:
            print(f"already exists: {lead['full_name']}")
        else:
            failed = True
            print(f"failed {lead['full_name']} ({status}): {result}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
