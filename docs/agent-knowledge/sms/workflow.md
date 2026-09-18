# SMS Engine — Workflow

## Outbound message flow

1. An authenticated user creates a conversation or bulk campaign from the SMS workspace.
2. The SMS API validates the lead, campaign snapshot, and consent state.
3. The API saves the conversation and queues work on `sms.conversations`.
4. The SMS worker prepares the next message and calls the TPI internal SMS send endpoint.
5. TPI selects the configured transport: Twilio for live delivery or mock SMS for local testing.
6. The provider result is normalized, returned to the SMS Engine, and stored with the message.
7. The inbox receives an update over the conversation WebSocket.

## Inbound Twilio flow

1. Twilio posts the incoming message to `POST /api/v1/provider/twilio/sms/inbound` on the public TPI URL.
2. TPI verifies `X-Twilio-Signature` against the exact public webhook URL.
3. TPI identifies the customer from the receiving number and normalizes the event.
4. TPI forwards it to `POST /api/v1/internal/sms/events/inbound` on the SMS Engine using the SMS internal service token.
5. The SMS Engine applies consent and opt-out rules, stores the inbound message, and queues the next action when appropriate.

## Delivery-status flow

1. Twilio posts status changes to `POST /api/v1/provider/twilio/sms/status` on TPI.
2. TPI validates the signature and forwards a normalized event to `POST /api/v1/internal/sms/events/status`.
3. The SMS Engine updates the stored provider status and publishes the UI update.

```text
T Rex SMS UI -> SMS API -> SMS worker -> TPI -> Twilio -> Lead
                                              ^          |
                                              | webhook  |
                                              +----------+
```
