# Calling Engine — Workflow

## Outbound Call Flow

1. Campaign scheduler dispatches `calling.start_outbound_call` Celery task
2. Task calls `CallingService.start_outbound_call()`
3. Service calls `TPIVoiceClient.start_call()` — HTTP request to TPI engine
4. TPI engine calls Vapi API with assistant configuration and lead variables
5. Vapi initiates the call to the lead phone number
6. TPI returns a normalized result with `provider_call_id`
7. Calling Engine saves a `QUEUED` call record to the database

## Webhook Flow (call completion)

1. Vapi fires event to TPI webhook endpoint (`POST /api/v1/tpi/webhooks/vapi/events`)
2. TPI verifies Vapi HMAC signature
3. TPI deduplicates the event
4. TPI forwards normalized event to Calling Engine (`POST /api/v1/webhooks/vapi/events`)
5. Calling Engine business-deduplicates via `seen_webhook_events` table
6. Calling Engine updates call record: status, transcript, summary, duration
7. Outcome is classified from transcript using `classify_outcome()`
8. Updated call record persisted

## KB Retrieval During Call

When the Vapi assistant needs to answer a question about the client company:
1. Vapi calls TPI KB tool endpoint
2. TPI validates context and calls Scraper Engine public Client-KB API
3. Results returned to Vapi in real time

## Campaign Trigger

```
Campaign Orchestrator
    |
    v (Celery task: calling.start_outbound_call)
CallingService
    |
    v (HTTP: TPI internal voice API)
TPI Engine
    |
    v (HTTP: Vapi API)
Vapi
    |
    v (phone call)
Lead
```
