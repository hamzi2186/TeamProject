# T Rex SMS Engine

Standalone SMS conversation module with a React frontend, FastAPI API, Celery worker, Redis-backed WebSocket events, and SMS-owned Postgres migrations.

## Ownership

- `sms-engine` owns conversation logic, consent, outcomes, persistence, Groq prompts, and Groq credentials.
- `tpi-engine` owns Twilio credentials, sending, webhook signature validation, and provider event normalization.
- Root platform teams own users, HubSpot leads, campaigns, and Client KB retrieval.

This module intentionally keeps its LLM provider inside the module instead of TPI. Each communication module supplies its own LLM provider and key.

## Local run

```bash
cp sms-engine/.env.example sms-engine/.env
docker compose --env-file sms-engine/.env -f sms-engine/docker-compose.yml up --build
```

Open `http://localhost:5174`. The local UI uses the configured demo user UUID. Starting autonomous outreach requires `GROQ_API_KEY`; real delivery additionally requires Twilio credentials and a US SMS-capable sender.

## Dummy campaign and mock SMS

Local Compose defaults to `SMS_PROVIDER=mock`, so the Groq conversation can be tested
without Twilio. Seed the internal campaign fixture:

```bash
python3 sms-engine/scripts/seed_demo_campaign.py
```

Captured outbound messages are visible in the conversation UI and through:

```bash
curl http://localhost:8001/api/v1/mock/sms/messages
```

Simulate a reply from the lead:

```bash
curl -X POST http://localhost:8001/api/v1/mock/sms/reply \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "33333333-3333-4333-8333-333333333333",
    "from_number": "+15555550111",
    "to_number": "+15555550100",
    "body": "Yes, what does it cost?"
  }'
```

Set `SMS_PROVIDER=twilio` when live credentials and a sender number are available.

## Bulk campaigns

`POST /api/v1/sms/conversations/bulk` accepts a campaign snapshot plus up to 500
selected leads. It loads existing conversations and consent records in batches,
creates missing conversations in one transaction, and queues workers only after
the commit succeeds. Opted-out and non-consented leads are skipped. The local UI
uses the demo HubSpot fixture; the shared contacts API can later send the same
lead contract without changing the SMS engine.

## Provider webhooks

Expose TPI port `8001` through an HTTPS tunnel and configure:

```text
Incoming message: POST {PUBLIC_WEBHOOK_BASE_URL}/api/v1/provider/twilio/sms/inbound
Status callback:   POST {PUBLIC_WEBHOOK_BASE_URL}/api/v1/provider/twilio/sms/status
```

TPI validates `X-Twilio-Signature` using the exact public URL before forwarding normalized events.

## Checks

```bash
python -m pip install -r sms-engine/backend/requirements-dev.txt
python -m pytest sms-engine/backend/tests
python -m ruff check sms-engine/backend/app sms-engine/backend/tests
cd sms-engine/frontend && npm install && npm run build
```
