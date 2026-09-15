# T Rex Phase 1 Foundation

Phase 1 provides shared first-party authentication, a real Supabase PostgreSQL/Alembic foundation, Redis/Celery, the root auth frontend, and the internal TPI SMTP adapter. It does not use Supabase Auth, and root Auth never connects to SMTP directly.

## Local configuration

The existing gitignored files are authoritative for this development checkout:

- `backend/.env`: Supabase Session Pooler database URL, Redis URL, and TPI internal settings.
- `tpi-engine/backend/.env`: real SMTP settings and the matching internal service token.

Never commit either file. Examples intentionally contain no credential values. RS256 keys are generated on first backend start under the gitignored `backend/.secrets/` directory.

## Integrated runtime

```powershell
docker compose build
docker compose up -d redis tpi backend worker frontend
docker compose ps
```

Endpoints:

- Root frontend: `http://localhost:5173`
- Root backend health: `http://localhost:8000/health`
- Real database health: `http://localhost:8000/health/db`
- TPI health: `http://localhost:8001/health`

Run the migration explicitly when needed:

```powershell
docker compose run --rm backend alembic upgrade head
```

Verify the database and real SMTP delivery:

```powershell
python scripts/verify_database.py
python scripts/smtp_smoke_test.py
```

The SMTP check sends through `TPI API -> configured SMTP server` to the configured sender mailbox. It does not print the address or credentials.

## Interactive authentication smoke test

With the services running:

```powershell
python scripts/auth_smoke_test.py
```

Use an email address you can access. The script performs:

```text
register -> real database user -> TPI/SMTP OTP -> human OTP entry
         -> verify -> login -> /auth/me -> refresh rotation -> logout
```

The OTP is entered interactively and is not stored in source or written to disk.

## Development checks

```powershell
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests
python -m ruff check backend/app backend/tests tpi-engine/backend/app scripts
cd frontend
npm install
npm run build
```
