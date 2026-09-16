# T Rex Scraper Engine

The Scraper Engine turns a tenant-owned public website into a reusable Client Knowledge Base. It normalizes and deduplicates the site, crawls safe same-site pages, extracts useful text, creates deterministic chunks, requests embeddings through TPI, stores vectors in shared PostgreSQL/pgvector, and exposes tenant-scoped retrieval.

## Architecture

```text
Scraper frontend -> Scraper API -> Redis/Celery worker
                                  -> safe crawler/extractor/chunker
                                  -> TPI Embeddings -> Jina or configured local fallback
                                  -> shared PostgreSQL + pgvector

Calling/SMS/Mailer -> Scraper internal Client-KB HTTP API
```

Jina URLs, request schemas, API keys, retries, and provider errors exist only in TPI. The Scraper backend has no Jina credential or provider client.

Screenshots, color analysis, and logo extraction are not part of the Master PRD's detailed Scraper requirements, so this implementation does not add an unrelated visual-analysis pipeline.

## Configure

Copy examples and fill secrets locally. Never commit `.env` files.

```powershell
Copy-Item scraper-engine/backend/.env.example scraper-engine/backend/.env
Copy-Item scraper-engine/frontend/.env.example scraper-engine/frontend/.env
```

Required Scraper backend values:

- shared `DATABASE_URL`
- shared `REDIS_URL`
- `TPI_API_BASE_URL` and matching `TPI_INTERNAL_SERVICE_TOKEN`
- root `AUTH_JWKS_URL`, issuer, and audience
- a strong `SCRAPER_INTERNAL_SERVICE_TOKEN`

Jina configuration belongs only in `tpi-engine/backend/.env`.

## Integrated start

From the repository root:

```powershell
docker compose build tpi backend scraper-backend scraper-worker scraper-frontend
docker compose up -d redis tpi backend scraper-backend scraper-worker scraper-frontend
docker compose ps
```

Open `http://localhost:5174/knowledge`. The frontend reuses the root platform access token stored under `trex_access_token`; it does not implement another login system.

## Standalone start

Configure `scraper-engine/backend/.env` with reachable root JWKS, TPI, shared database, and Redis URLs, then:

```powershell
Set-Location scraper-engine
docker compose up -d --build
```

## Development checks

```powershell
& .venv/Scripts/python.exe -m pip install -r scraper-engine/backend/requirements-dev.txt
Set-Location scraper-engine/backend
& ../../.venv/Scripts/python.exe -m pytest -q
& ../../.venv/Scripts/python.exe -m ruff check app tests
Set-Location ../frontend
npm install
npm run build
```

The full Client KB contract is documented in `docs/api/client-kb.md`.

