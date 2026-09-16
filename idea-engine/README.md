# T Rex — Idea Engine (Lead Intelligence & Daily Reporting)

## 1. Overview
The **Idea Engine** is the central lead-intelligence and daily reporting engine for the **T Rex** multi-channel autonomous outreach platform.

It aggregates normalized interaction history across **Calling**, **SMS**, and **Mailer** from the shared Supabase PostgreSQL database, reconciles canonical lead outcomes, synthesizes multi-channel approach narratives, and generates end-of-day downloadable `.docx` lead intelligence reports.

## 2. Core Responsibilities
- **Multi-Channel Timeline Aggregation**: Combines touchpoints from `calls`, `sms_messages`, and `emails` into a unified chronological journey per lead.
- **Canonical Outcome Evaluation**: Strictly evaluates lead outcomes according to the platform hierarchy:
  `DO_NOT_CONTACT > CONVERTED > INTERESTED > FOLLOW_UP_REQUIRED > NOT_INTERESTED > NO_ANSWER > NO_RESPONSE > CONTACTING > NEW`
- **Conversation & Journey Synthesizer**: Produces concise executive summaries and approach sequence timelines based on factual persisted database records (with optional TPI LLM enhancement).
- **DOCX Report Generation**: Built locally with `python-docx` (no external vendor API required) conforming to T Rex brand styling.
- **Scheduled & On-Demand Execution**: Automated end-of-day execution via Celery Beat or on-demand via `POST /idea/reports/daily/generate`.
- **Page 18 Frontend UI**: Dedicated React + Vite + TypeScript interface (`/reports`, `/reports/:reportId`, `/reports/leads/:leadId`) styled according to the locked T Rex design tokens.

## 3. Strict Isolation Rules
- **No private code imports** from `calling-engine`, `sms-engine`, or `mailer-engine`.
- **No direct vendor SDKs** (no Twilio, Vapi, or Resend code). All vendor interactions are isolated in TPI.
- **No provider webhooks**. TPI normalizes all external events.
- **Local DOCX Generation**: Rendered directly in Python without third-party vendor APIs.

## 4. API Endpoints
All endpoints return the standard envelope `{ "success": true, "data": ..., "error": null, "request_id": "..." }`:
- `POST /idea/reports/daily/generate` — Trigger on-demand report generation for a given date (default today).
- `GET  /idea/reports/daily` — List historical reports with outcome KPI summaries.
- `GET  /idea/reports/{report_id}` — Get report detail and per-lead items.
- `GET  /idea/reports/{report_id}/download` — Download generated `.docx` report.
- `GET  /idea/leads/{lead_id}/summary` — Real-time lead 360° journey and outcome breakdown.
- `GET  /health` — Service health check.

## 5. Quick Start (Local Development)

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

### Seed Demo Data & Generate Sample Report
```bash
python3 idea-engine/scripts/seed_demo_data.py
```

### Standalone Docker Runtime
```bash
cd idea-engine
docker compose up --build
```
