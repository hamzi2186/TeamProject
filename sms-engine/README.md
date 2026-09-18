# T Rex SMS Engine

SMS conversation module with a React frontend, FastAPI API, Celery worker, and Redis-backed WebSocket events. It runs inside the unified T Rex stack and also supports an isolated local-development stack.

## Ownership

- `sms-engine` owns conversation logic, consent, outcomes, persistence, and SMS decision prompts.
- `tpi-engine` owns Twilio and Groq credentials, provider calls, webhook signature validation, and normalized provider responses.
- Root platform teams own users, HubSpot leads, campaigns, and Client KB retrieval.
- `backend/alembic` owns the canonical shared-database migration chain used by the integrated stack.
- `sms-engine/backend/alembic` exists only for the isolated local Postgres workflow.

The SMS worker calls TPI's internal LLM contract for generated decisions and TPI's internal SMS contract for delivery. No third-party provider SDK or credential belongs in this module.

## Unified T Rex run

The root `docker-compose.yml` uses the canonical `backend/.env` database connection, so SMS shares the same Supabase project as the other engines. The root backend applies the canonical migration chain before SMS starts.

```bash
TPI_API_BASE_URL=https://trex-central-tpi.onrender.com \
  docker compose up --build backend sms-backend sms-worker sms-frontend frontend \
  --scale tpi=0
```

Open the platform at `http://localhost:5173` and choose **SMS Engine**. The unified route is `http://localhost:5173/sms/`; direct SMS frontend access is available at `http://localhost:5175/sms/`.

## Isolated local run

```bash
cp sms-engine/.env.example sms-engine/.env
docker compose --env-file sms-engine/.env -f sms-engine/docker-compose.yml up --build
```

Open `http://localhost:5174/sms/`. The isolated stack uses local Postgres on port `5433`, Redis on `6380`, the SMS API on `8002`, and the TPI API on `8001`. It is for module development only and is not the instructor-required integrated database topology.

Starting autonomous outreach requires TPI's LLM provider to be configured. Real delivery additionally requires Twilio credentials and an SMS-capable sender configured only in TPI.

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

Set `SMS_PROVIDER=twilio` only in TPI when live credentials and a sender number are available. Keep `mock` for safe route and workflow testing.

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

## Repository layout

- `backend/` — SMS API, workers, domain models, and isolated migration metadata
- `frontend/` — SMS inbox and campaign UI mounted at `/sms/`
- `scripts/` and `fixtures/` — isolated demo support
- `../contracts/` — shared cross-engine and TPI contracts
- `../tpi-engine/` — Twilio adapter and provider-facing webhooks
- `../docs/agent-knowledge/sms/` — Agent Engine product knowledge
- `../backend/alembic/versions/20260918_0008_sms_engine.py` — canonical shared migration

Provider adapters must remain in TPI, and other engines must communicate with SMS through HTTP contracts rather than importing SMS internals.

## Checks

```bash
python -m pip install -r sms-engine/backend/requirements-dev.txt
python -m pytest sms-engine/backend/tests
python -m ruff check sms-engine/backend/app sms-engine/backend/tests
cd sms-engine/frontend && npm install && npm run build
```
