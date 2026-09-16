# Calling Engine — Usage

## Viewing Calls

Navigate to `/calling` in the T Rex frontend.

You can filter by:
- **Status**: QUEUED, RINGING, IN_PROGRESS, COMPLETED, NO_ANSWER, FAILED, CANCELLED
- **Outcome**: INTERESTED, NOT_INTERESTED, FOLLOW_UP_REQUIRED, CONVERTED, NO_ANSWER, DO_NOT_CONTACT
- **Lead ID**: search by the lead identifier

## Call Detail

Click any row to open the detail view showing:
- Call status and outcome
- Duration and timestamps
- Full transcript
- AI summary
- Recording (if enabled)

## Starting Calls

Calls are started automatically by the campaign system. To trigger a call for a lead:
1. Create a campaign with the Calling channel enabled
2. Add leads to the campaign
3. Run the campaign

## Phone Number Format

All phone numbers must be in E.164 format (e.g., `+12125551234`).

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | /api/v1/calling/calls | List all calls for the authenticated user |
| GET | /api/v1/calling/calls/{call_id} | Get a single call record |
| POST | /api/v1/calling/tools/search-client-kb | KB search tool (used by Vapi during calls) |
| POST | /api/v1/webhooks/vapi/events | Internal webhook from TPI (not customer-facing) |
