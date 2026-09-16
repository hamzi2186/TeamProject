# Mailer overview

The Mailer Engine is the email outreach and reply automation component for T Rex. It keeps the outbound and inbound email flows grounded in the lead's client knowledge base and persists the thread to support follow-up and outcome classification.

## Responsibilities

- Send personalized outbound campaign emails
- Correlate inbound replies to a valid conversation
- Use the lead's context and Client KB to generate intelligent follow-ups
- Track message delivery and webhook events
- Stop communication on explicit opt-out and hard-failure conditions
- Persist the evolving conversation history for dashboard visibility

## Provider boundary

The Mailer Engine uses the shared TPI layer and never directly imports Resend or vendor-specific SDK logic.
