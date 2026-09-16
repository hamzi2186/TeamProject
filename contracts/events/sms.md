# SMS internal events

TPI forwards events to the SMS engine using `X-SMS-Service-Token`.

## Inbound message

`POST /api/v1/internal/sms/events/inbound`

```json
{
  "provider": "twilio",
  "event_id": "SM...",
  "user_id": "33333333-3333-4333-8333-333333333333",
  "provider_message_id": "SM...",
  "from_number": "+15555550101",
  "to_number": "+15555550100",
  "body": "Yes, tell me more",
  "occurred_at": "2026-09-16T12:00:00Z",
  "raw_payload": {}
}
```

## Delivery status

`POST /api/v1/internal/sms/events/status`

```json
{
  "provider": "twilio",
  "event_id": "SM...:DELIVERED",
  "user_id": "33333333-3333-4333-8333-333333333333",
  "provider_message_id": "SM...",
  "status": "DELIVERED",
  "error_code": null,
  "occurred_at": "2026-09-16T12:00:02Z",
  "raw_payload": {}
}
```

Events are idempotent by `(provider, event_id)`.
