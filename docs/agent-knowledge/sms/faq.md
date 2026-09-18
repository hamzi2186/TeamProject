# SMS Engine — FAQ

**Q: Does the SMS Engine store Twilio credentials?**  
A: No. Twilio credentials are owned by the TPI Engine and must remain in its ignored environment file.

**Q: Why is a conversation not sending?**  
A: Check that the lead has consent, is not opted out, the worker is running, the SMS and TPI service tokens match, and the selected transport is configured. In Twilio mode, also verify the sender number is SMS-capable.

**Q: Can I test without sending a real SMS?**  
A: Yes. Set the transport to `mock`. This tests the SMS application and its TPI boundary without contacting Twilio.

**Q: Where should Twilio webhooks point?**  
A: Point incoming messages to `/api/v1/provider/twilio/sms/inbound` and status callbacks to `/api/v1/provider/twilio/sms/status` on the public HTTPS URL for TPI, not the SMS backend.

**Q: Why does TPI reject a Twilio webhook signature?**  
A: Twilio signs the exact externally visible URL. Ensure `PUBLIC_WEBHOOK_BASE_URL`, scheme, host, path, query string, and proxy forwarding match the URL configured in Twilio.

**Q: What happens when a lead replies STOP?**  
A: The SMS Engine records the opt-out and prevents additional automated sends for that recipient.

**Q: Why is the AI not generating the next reply?**  
A: Confirm the SMS worker is consuming `sms.conversations`, the conversation is active and consented, and the SMS Engine's configured language-model provider is available. Provider credentials for message generation belong to the SMS module, while Twilio remains in TPI.
