# Calling Engine — Overview

The T Rex Calling Engine manages outbound and inbound AI voice calls for lead outreach campaigns.

## What it does

- Initiates outbound AI voice calls to leads as part of campaigns
- Tracks call state (queued, ringing, in progress, completed, failed)
- Persists call transcripts and summaries after each call
- Classifies lead outcomes from call transcripts
- Exposes a Client Knowledge Base (KB) tool for the AI voice agent to answer lead questions during calls

## What it does NOT do

- The Calling Engine does not manage Vapi or Twilio accounts, credentials, or configuration — that belongs to the TPI Engine
- The Calling Engine does not issue JWTs or manage user accounts — that belongs to the root platform auth
- Customers cannot dial arbitrary numbers through the Calling Engine — calls are only started by the campaign scheduler

## How calls start

Calls are started by the shared campaign orchestrator via the `calling.start_outbound_call` Celery task. This task calls the TPI Engine's internal voice API, which then calls Vapi or Twilio.

## Call outcomes

After a call completes, the engine classifies the outcome from the transcript:

| Outcome | Meaning |
|---|---|
| INTERESTED | Lead expressed interest |
| NOT_INTERESTED | Lead explicitly refused |
| FOLLOW_UP_REQUIRED | Lead asked to reconnect later |
| CONVERTED | Campaign target action achieved |
| NO_ANSWER | Call was not picked up |
| DO_NOT_CONTACT | Lead asked to stop all contact |
| COMPLETED | Call ended without clear classification |
| FAILED | Technical failure |
