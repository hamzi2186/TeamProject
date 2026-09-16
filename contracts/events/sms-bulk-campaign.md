# SMS bulk campaign contract

`POST /api/v1/sms/conversations/bulk`

The caller supplies a campaign snapshot and selected leads. Lead data may come
from HubSpot, another CRM, or a local fixture; the SMS engine does not depend on
the source-specific schema.

```json
{
  "campaign_id": "44444444-4444-4444-8444-444444444444",
  "from_number": "+15555550100",
  "message_template": "Hi {{first_name}}, are you still interested?",
  "campaign_objective": "Book a product demonstration.",
  "knowledge_context": "Approved campaign facts.",
  "max_agent_turns": 6,
  "start_immediately": true,
  "leads": [
    {
      "lead_id": "55555555-5555-4555-8555-555555555555",
      "first_name": "Sam",
      "contact_name": "Sam Carter",
      "phone_number": "+15555550111",
      "timezone": "America/Los_Angeles",
      "consented": true,
      "consent_source": "hubspot_import"
    }
  ]
}
```

The response separates newly created conversation IDs, queued conversation IDs,
and skipped leads with reasons such as `NO_CONSENT`, `OPTED_OUT`,
`ALREADY_STARTED`, or `NOT_OPEN`.
