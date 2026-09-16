# T Rex TPI Engine

Internal-only provider boundary. It currently implements SMTP email delivery and the Twilio SMS adapter. It has no customer-facing frontend.

Run from `tpi-engine/backend` with its gitignored `.env`:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

All delivery calls require `X-TPI-Service-Token`. Provider credentials remain in this service only.

Twilio webhooks terminate here. TPI validates `X-Twilio-Signature`, maps the receiving number to a customer, and forwards normalized events to the SMS engine. Groq is intentionally not configured here; each communication engine owns its own LLM provider.
