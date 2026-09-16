# Mailer workflow

## Outbound

1. Validate the authenticated user, campaign, and lead.
2. Open or resume the email conversation.
3. Retrieve the Client KB for that lead and campaign context.
4. Generate a personalized subject and body.
5. Send through TPI/Resend.
6. Persist message metadata and message IDs.
7. Mark the conversation as waiting for the lead response.

## Inbound

1. Receive a Resend webhook.
2. Persist the webhook event idempotently.
3. Correlate the message with a conversation using Reply-To, In-Reply-To, References, or provider IDs.
4. Save the inbound email event.
5. Retrieve the relevant Client KB and recent thread context.
6. Generate a structured AI reply and outcome.
7. Send the response through TPI.
8. Save the outbound message.
9. Continue or stop based on the outcome.
