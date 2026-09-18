# SMS Engine — Overview

The T Rex SMS Engine manages consent-aware, two-way SMS outreach conversations for campaign leads.

## What it does

- Creates individual or bulk SMS conversations from campaign and lead snapshots
- Queues autonomous replies and advances conversation state through a Celery worker
- Stores messages, delivery status, consent state, and conversation outcomes
- Streams conversation updates to the inbox over WebSockets
- Supports a mock transport for safe local testing and Twilio for live delivery

## Service ownership

- The SMS Engine owns conversation orchestration, consent checks, opt-out handling, outcomes, persistence, and message generation.
- The TPI Engine owns Twilio credentials, outbound provider calls, webhook signature verification, and provider-event normalization.
- The root platform owns authentication, users, campaigns, leads, and shared customer data.

The SMS Engine never calls Twilio directly. It sends normalized requests to the TPI internal SMS API with a service token. TPI forwards normalized inbound and status events back to the SMS Engine.

## Conversation outcomes

Common terminal or business outcomes include interested, follow-up required, converted, not interested, opted out, completed, and failed. An opt-out immediately prevents further automated messages for that recipient.
