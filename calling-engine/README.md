# T Rex — Calling Engine (Standalone & Shared)

Autonomous voice-agent orchestration layer for the T Rex Operations Platform. Powered by Vapi AI and Telnyx telephony via the TPI gateway.

## Features

- **Outbound Voice Dispatch**: Initiates calls to leads using verified phone numbers (`+14069571074`).
- **AI Voice Agent**: Configured with Vapi AI Voice Assistant (`T Rex`).
- **Real-Time Tracking & Webhooks**: Ingests normalized call events, status transitions, duration, audio recordings, and transcripts.
- **Outcome Classification**: Automatic categorization (`INTERESTED`, `CONVERTED`, `CALLBACK_REQUESTED`, `NOT_INTERESTED`, `BUSY`, `FAILED`, `VOICEMAIL`).
- **Client Knowledge Base**: Queries company website intelligence through the Scraper Client KB contract (`/tools/search-client-kb`).
- **Shared Supabase / PostgreSQL**: Runs with one unified Alembic migration chain (`20260916_0006_calling_foundation`).

## Running Standalone

### 1. Backend
```bash
cd calling-engine/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

### 2. Frontend
```bash
cd calling-engine/frontend
npm install
npm run dev
```

### 3. Docker Compose
```bash
cd calling-engine
docker compose up --build
```

- Standalone UI: [http://localhost:5174](http://localhost:5174)
- Standalone API Docs: [http://localhost:8002/docs](http://localhost:8002/docs)
- Main Platform UI: [http://localhost:5173/calling](http://localhost:5173/calling)
