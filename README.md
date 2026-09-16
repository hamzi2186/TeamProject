# T Rex — Calling Engine

Outbound and inbound AI voice call management for the T Rex platform.

## Architecture

```
Campaign Scheduler (root platform)
    |
    v (Celery task: calling.start_outbound_call)
Calling Engine Backend  :8002
    |
    v (HTTP + X-TPI-Service-Token)
TPI Engine  :8001
    |
    v (HTTPS)
Vapi API
    |
    v (phone call + webhooks back through TPI)
Lead
```

**The Calling Engine never calls Vapi directly.** All voice provider operations go through the TPI Engine per the T Rex architecture.

## Quick Start (standalone dev)

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL (shared with root platform)
- Redis
- TPI Engine running on port 8001

### 1. Configure environment

```powershell
Copy-Item .env.example .env
# Edit .env with your database URL, TPI token, and auth public key
```

### 2. Copy auth public key

The Calling Engine needs the public key from the root platform to verify JWTs:

```powershell
New-Item -ItemType Directory -Force .secrets
# Copy auth_public.pem from root platform's .secrets/ directory
Copy-Item ..\TeamProjectRepo\.secrets\auth_public.pem .secrets\
```

### 3. Run migrations

```powershell
cd backend
pip install -r requirements.txt
alembic upgrade head
```

### 4. Start backend

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

### 5. Start worker

```powershell
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO -Q calling.calls
```

### 6. Start frontend

```powershell
cd frontend
npm install
npm run dev
# Opens at http://localhost:5174/calling
```

## Docker (integrated)

This engine is part of the root platform `docker-compose.yml`. Add the calling services to the root compose:

```powershell
# From root platform directory
docker compose up --build calling-backend calling-worker calling-frontend
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Liveness check |
| GET | `/health/db` | None | DB connectivity |
| GET | `/api/v1/calling/calls` | Bearer JWT | List calls |
| GET | `/api/v1/calling/calls/{call_id}` | Bearer JWT | Get call |
| POST | `/api/v1/calling/tools/search-client-kb` | Bearer JWT | KB tool |
| POST | `/api/v1/webhooks/vapi/events` | Internal | TPI → engine webhook |

## Frontend Routes

| Path | Description |
|---|---|
| `/calling` | Call list with filters |
| `/calling/:callId` | Call detail (transcript, summary, outcome) |

## Auth

The Calling Engine is a **token consumer**. It verifies RS256 JWTs issued by the shared root platform. It never issues tokens or manages users.

The frontend reads `trex_access_token` from `sessionStorage` (set by the root auth flow).

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

## Agent Knowledge

This engine maintains documentation for the T Rex Assistant (Agent Engine) in:

```
docs/agent-knowledge/calling/
├── overview.md
├── workflow.md
├── usage.md
└── faq.md
```
