# T Rex TPI Engine

Internal-only provider boundary. Phase 1 implements the real SMTP email-delivery adapter used by root authentication. It has no customer-facing frontend.

Run from `tpi-engine/backend` with its gitignored `.env`:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

All delivery calls require `X-TPI-Service-Token`. Provider credentials remain in this service only.
