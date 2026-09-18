# T Rex — Idea Engine (Lead Intelligence & Daily Reporting)

## 1. Overview
The **Idea Engine** is the central lead-intelligence and daily reporting engine for the **T Rex** multi-channel autonomous outreach platform.

It aggregates normalized interaction history across **Calling**, **SMS**, and **Mailer** from the shared Supabase PostgreSQL database, reconciles canonical lead outcomes, synthesizes multi-channel approach narratives, and generates end-of-day downloadable `.docx` lead intelligence reports.

## 2. Core Responsibilities
- **Multi-Channel Timeline Aggregation**: Combines touchpoints from `calls`, `sms_messages`, and `emails` into a unified chronological journey per lead.
- **Canonical Outcome Evaluation**: Strictly evaluates lead outcomes according to the platform hierarchy (highest precedence first):
  `DO_NOT_CONTACT(100) > CONVERTED(90) > INTERESTED(80) > FOLLOW_UP_REQUIRED(70) > NOT_INTERESTED(60) > CONTACTING(50) > NO_ANSWER(40) > NO_RESPONSE(30) > FAILED(20) > COMPLETED(15) > NEW(10)`
- **Conversation & Journey Synthesizer**: Produces concise executive summaries and approach sequence timelines based on factual persisted database records (with optional TPI LLM enhancement).
- **DOCX Report Generation**: Built locally with `python-docx` (no external vendor API required) conforming to T Rex brand styling. Produces summary pages plus one dedicated page per lead (factual event log, campaigns, generated narrative, outcome evidence, next action).
- **Scheduled & On-Demand Execution**: Automated execution via Celery Beat at exactly **00:00 UTC** each day, reporting on the **previous day** for **every lead** in the database (or on-demand via `POST /idea/reports/daily/generate`).
- **Page 18 Frontend UI**: Dedicated React + Vite + TypeScript interface (`/reports`, `/reports/:reportId`, `/reports/leads/:leadId`) styled according to the locked T Rex design tokens.

## 3. Strict Isolation Rules
- **No private code imports** from `calling-engine`, `sms-engine`, or `mailer-engine`.
- **No direct vendor SDKs** (no Twilio, Vapi, or Resend code). All vendor interactions are isolated in TPI.
- **No provider webhooks**. TPI normalizes all external events.
- **Local DOCX Generation**: Rendered directly in Python without third-party vendor APIs.

## 4. API Endpoints
All endpoints return the standard envelope `{ "success": true, "data": ..., "error": null, "request_id": "..." }`:
- `POST /idea/reports/daily/generate` — Trigger on-demand report generation for a given date (default today UTC; passing an explicit date like `2026-09-17` reports that day).
- `GET  /idea/reports/daily` — List historical reports with outcome KPI summaries.
- `GET  /idea/reports/{report_id}` — Get report detail and per-lead items.
- `GET  /idea/reports/{report_id}/download` — Download generated `.docx` report.
- `GET  /idea/leads/{lead_id}/summary` — Real-time lead 360° journey and outcome breakdown.
- `GET  /health` — Service health check.

## 5. Quick Start (Local Development)

### Prerequisites

- **Shared Supabase PostgreSQL** configured via `DATABASE_URL` (copy `.env.example` → `.env`; see the Docker section below). The shared platform tables (`leads`, `calls`, `sms_messages`, `emails`, `campaigns`, `conversations`) are owned and migrated by the root backend; Idea Engine only materializes its own two tables (`idea_report_runs`, `idea_lead_report_items`) plus its isolated `alembic_version_idea` migration chain. Campaign enrichment is best-effort and degrades gracefully when the `campaigns` table is unavailable.
- **TPI** (Third-Party Integrations) serves **optional** LLM conversation synthesis. If a shared/deployed TPI (port 8001) is available, set `TPI_API_BASE_URL` + `TPI_INTERNAL_SERVICE_TOKEN`. When unset, the pipeline uses deterministic summaries (no latency, still fully functional).

### Backend
```bash
cd idea-engine/backend
uv run uvicorn app.main:app --port 8006 --reload
```

### Frontend
```bash
cd idea-engine/frontend
npm install
npm run dev
# Open http://localhost:5176/reports
```

### Run Tests
```bash
uv run --project idea-engine/backend --extra dev pytest idea-engine/backend/tests
```

### Verify a Generated Report Against Raw Data
```bash
uv run --project idea-engine/backend python idea-engine/scripts/verify_report_against_raw.py --report-date 2026-09-18
```

### Generate a Report
POST `/idea/reports/daily/generate` on the backend (`:8006`). Runs are idempotent per
report date; the daily schedule re-triggers this automatically.

## 6. Docker (Team Onboarding)

The compose stack is **self-contained** (bundles its own internal Redis) and connects
every member to the **same shared Supabase database**. Only `DATABASE_URL` is required;
TPI and the daily scheduler are opt-in.

### 1. Configure

```bash
cd idea-engine
cp .env.example .env
# Edit .env → set DATABASE_URL to the shared Supabase connection string.
# Optionally set TPI_API_BASE_URL / TPI_INTERNAL_SERVICE_TOKEN for LLM summaries.
```

### 2. Build & start

```bash
docker compose up --build -d --wait
docker compose ps        # all three services should be "healthy"
```

- UI: http://localhost:5176 (API and DOCX downloads are same-origin via nginx → no CORS)
- Backend API: http://localhost:8006 · health: http://localhost:8006/health

### 3. Use it

- Generate today's report on demand from the UI button or
  `curl -X POST http://localhost:8006/idea/reports/daily/generate`
- Download the `.docx` from the report detail page.

### 4. Daily 00:00 UTC scheduler (opt-in)

The Celery worker runs **only** under the `scheduler` profile, so teammates don't race
the same shared report row every midnight. Nominate **one** machine to own the schedule:

```bash
docker compose --profile scheduler up -d
```

Other members run plain `docker compose up` (no cron; on-demand generation covers them).

### 5. Troubleshooting

- **`DATABASE_URL is required`** → you ran before copying `.env.example` to `.env` and
  filling in the Supabase credentials.
- **Port conflict** → the host already runs these ports; use
  `BACKEND_PORT=8106 FRONTEND_PORT=5276 docker compose up ...`.
- **Slow report generation** → an unreachable `TPI_API_BASE_URL` adds timeouts; leave it
  empty unless a shared TPI is available.
