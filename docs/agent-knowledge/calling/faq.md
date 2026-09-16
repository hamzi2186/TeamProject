# Calling Engine — FAQ

**Q: How do I start a call to a specific lead?**
A: Calls are only started by the campaign scheduler. Create a campaign, add the lead, and run the campaign with the Calling channel enabled.

**Q: Why did a call show as NO_ANSWER?**
A: The call was connected to the lead phone number but was not answered before the timeout. The Vapi voice agent hung up after the configured ring duration.

**Q: What does DO_NOT_CONTACT mean?**
A: During the call, the lead explicitly asked to stop receiving calls (e.g., said "stop", "do not call", "unsubscribe"). The platform will prevent future automated calls to this lead.

**Q: Where is the call recording?**
A: Recording is optional and must be configured in Vapi. If a recording URL is available, it will appear on the Call Detail page.

**Q: Can I see who the AI voice agent is?**
A: The voice assistant is configured in Vapi by the platform administrator. The Calling Engine passes the lead context (name, company info from KB, campaign goal) to the assistant.

**Q: How long does it take for a transcript to appear?**
A: Transcripts are available after Vapi sends the end-of-call webhook, usually within a few seconds of the call ending.

**Q: What is the Client KB tool?**
A: During a call, the Vapi assistant can search the lead company knowledge base (built by the Scraper Engine) to answer factual questions about the client company. This prevents the AI from hallucinating facts.
