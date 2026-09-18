# SMS Engine — Usage

## Opening the workspace

Sign in to the T Rex platform and choose **SMS Engine** from the dashboard or sidebar. The unified route is `/sms/` on the platform origin.

## Working with conversations

- Select a conversation to review the complete message history and current outcome.
- Search and filter the inbox to find a lead or conversation.
- Use the composer for a manual reply when the conversation is eligible to receive messages.
- Start a bulk campaign by selecting leads and providing the campaign snapshot required by the SMS API.
- Observe new messages and delivery changes in real time through the workspace connection indicator.

## Consent and opt-out

Only contact leads with the required SMS consent. Standard opt-out language such as `STOP` records the opt-out and blocks additional automated sends. Do not bypass this state by creating another conversation.

## Local and live transports

Use `SMS_PROVIDER=mock` for development. Mock mode exercises the application and TPI routing without sending a real message. Live mode uses `SMS_PROVIDER=twilio`; Twilio credentials and the public webhook base URL belong only in the ignored TPI environment file.

## Relevant endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/sms/conversations` | List the authenticated user's conversations |
| POST | `/api/v1/sms/conversations` | Create a conversation |
| POST | `/api/v1/sms/conversations/bulk` | Create conversations for selected campaign leads |
| POST | `/api/v1/internal/sms/events/inbound` | Receive a normalized inbound event from TPI |
| POST | `/api/v1/internal/sms/events/status` | Receive a normalized delivery update from TPI |
| POST | `/api/v1/internal/sms/send` | TPI endpoint used by the SMS worker to send a message |

The internal endpoints require service credentials and are not customer-facing APIs.
