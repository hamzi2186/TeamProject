# SMS Engine Handoff

Branch: `feat/sms-engine`

The SMS engine is complete locally: React inbox, FastAPI API, PostgreSQL schema,
Celery workers, WebSockets, Groq replies, bulk campaign launch, consent/compliance,
and a local mock SMS transport with replies from the browser.

## Morning sync

```bash
git fetch origin
git switch feat/sms-engine
git merge origin/main
```

If the real KB/HubSpot work is on another branch, merge that branch instead of
waiting for `main`.

## Remaining integration

1. Map the shared HubSpot/contact records into the bulk contract documented in
   `contracts/events/sms-bulk-campaign.md`.
2. Replace each conversation's fixture `knowledge_context` with approved content
   returned by the shared KB service. The Groq agent already consumes this field.
3. Set `SMS_PROVIDER=twilio` and configure the Twilio SID, token, assigned SMS
   number, and public webhook URL in `sms-engine/.env`.
4. Configure Twilio inbound and status webhooks using the routes in
   `sms-engine/README.md`, then run one real US send/reply test.

Use `SMS_PROVIDER=mock` for local testing. Secrets belong only in the ignored
`.env` file. Run the Docker and test commands in `sms-engine/README.md` after
merging shared work.
