# TPI SMS contract

TPI owns Twilio credentials and provider-facing HTTP. The SMS engine never imports the Twilio SDK.

## Send

`POST /api/v1/internal/sms/send`

Header: `X-TPI-Service-Token`

```json
{
  "user_id": "33333333-3333-4333-8333-333333333333",
  "to_number": "+15555550101",
  "body": "Hi Sam, is this a good time to talk?"
}
```

```json
{
  "provider": "twilio",
  "provider_message_id": "SM...",
  "status": "QUEUED",
  "from_number": "+15555550100"
}
```

TPI resolves the sender from `user_id`. The caller cannot choose an arbitrary Twilio number.

For local development, set `SMS_PROVIDER=mock`. The same send contract then returns a
mock provider ID and `DELIVERED` without contacting Twilio. Captured outbound messages
are available at `GET /api/v1/mock/sms/messages`, and an inbound reply can be simulated
with `POST /api/v1/mock/sms/reply`.

## Provider webhooks

Twilio calls TPI only:

- `POST /api/v1/provider/twilio/sms/inbound`
- `POST /api/v1/provider/twilio/sms/status`

Both require a valid `X-Twilio-Signature`. TPI returns quickly after forwarding the normalized event to the SMS engine.
