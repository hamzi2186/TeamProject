# SMS Engine — Overview

The T Rex SMS Engine manages consent-aware, two-way SMS outreach conversations for campaign leads.

## What it does

- Creates individual or bulk SMS conversations from campaign and lead snapshots
- Queues autonomous replies and advances conversation state through a Celery worker
- Stores messages, delivery status, consent state, and conversation outcomes
- Streams conversation updates to the inbox over WebSockets
- Supports a mock transport for safe local testing and Twilio for live delivery

## Service ownership

- The SMS Engine owns conversation orchestration, consent checks, opt-out handling, outcomes, persistence, and SMS decision prompts.
- The TPI Engine owns Groq and Twilio credentials, LLM/provider calls, webhook signature verification, and provider-event normalization.
- The root platform owns authentication, users, campaigns, leads, and shared customer data.

The SMS Engine never calls Twilio directly. It sends normalized requests to the TPI internal SMS API with a service token. TPI forwards normalized inbound and status events back to the SMS Engine.

## Conversation outcomes

Supported business outcomes are `INTERESTED`, `CONVERTED`, `FOLLOW_UP_REQUESTED`, `NOT_INTERESTED`, `WRONG_NUMBER`, `DO_NOT_CONTACT`, and `NO_RESPONSE`. An opt-out immediately records `DO_NOT_CONTACT` and prevents further automated messages for that recipient.
