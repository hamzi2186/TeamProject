from uuid import uuid4

import pytest

from app.modules.mailer.service import MailerService


@pytest.mark.asyncio
async def test_mailer_service_flow_handles_outbound_then_inbound():
    service = MailerService(repository=None, email_provider=None)
    conversation = await service.open_conversation(
        user_id=uuid4(),
        lead_id=uuid4(),
        campaign_id=uuid4(),
        subject="Demo",
        status="WAITING_FOR_LEAD",
    )
    assert conversation["status"] == "WAITING_FOR_LEAD"
    event = await service.process_webhook_event(
        {
            "provider": "resend",
            "id": "evt-flow-1",
            "type": "inbound.received",
            "data": {
                "from": "lead@example.com",
                "to": ["mailer+abc123@reply.example.com"],
                "subject": "Re: Demo",
                "text": "Interested in a demo.",
            },
        }
    )
    assert event["status"] in {"processed", "duplicate"}
