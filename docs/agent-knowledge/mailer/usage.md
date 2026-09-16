# Mailer usage

## API

- GET /api/v1/mailer/conversations
- GET /api/v1/mailer/conversations/{conversation_id}
- POST /api/v1/webhooks/resend

## Typical flow

- Start a campaign that includes an email channel.
- Trigger the scheduled email action.
- The engine opens a conversation and sends the first message.
- Inbound replies are processed via Resend webhook callbacks.
- The lead's latest message is classified and the follow-up is sent automatically.

## Safety

- Enforce tenant ownership on every access.
- Do not correlate by subject alone.
- Stop on unsubscribe, negative outcome, or bounce.
