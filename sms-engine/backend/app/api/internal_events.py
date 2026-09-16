from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_internal_service
from app.db.session import get_db
from app.models.sms import SmsConsent, SmsConversation, SmsMessage, SmsProviderEvent
from app.schemas.sms import DeliveryStatusEvent, InboundSmsEvent, InternalEventResponse
from app.services.compliance import compliance_command
from app.services.events import publish_conversation_event
from app.workers.tasks import generate_and_send_reply

router = APIRouter(
    prefix="/api/v1/internal/sms",
    tags=["sms-internal"],
    dependencies=[Depends(require_internal_service)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/events/inbound", response_model=InternalEventResponse)
async def inbound_sms(payload: InboundSmsEvent, db: DbSession) -> InternalEventResponse:
    if await _duplicate(
        db,
        payload.user_id,
        payload.provider,
        payload.event_id,
        "inbound",
        payload.raw_payload,
    ):
        return InternalEventResponse(accepted=True, duplicate=True)
    conversation = await db.scalar(
        select(SmsConversation)
        .where(
            SmsConversation.user_id == payload.user_id,
            SmsConversation.from_number == payload.to_number,
            SmsConversation.to_number == payload.from_number,
            SmsConversation.status == "OPEN",
        )
        .order_by(SmsConversation.updated_at.desc())
        .limit(1)
    )
    if conversation is None:
        conversation = SmsConversation(
            user_id=payload.user_id,
            campaign_id=None,
            lead_id=None,
            contact_name="Unresolved sender",
            from_number=payload.to_number,
            to_number=payload.from_number,
            timezone="UTC",
            status="UNRESOLVED",
            message_template="",
            campaign_objective="Resolve the inbound sender before replying.",
            knowledge_context="",
        )
        db.add(conversation)
        await db.flush()
    message = SmsMessage(
        conversation_id=conversation.id,
        user_id=payload.user_id,
        lead_id=conversation.lead_id,
        direction="INBOUND",
        from_number=payload.from_number,
        to_number=payload.to_number,
        body=payload.body,
        provider=payload.provider,
        provider_message_id=payload.provider_message_id,
        delivery_status="RECEIVED",
        provider_payload=payload.raw_payload,
        occurred_at=payload.occurred_at,
    )
    db.add(message)
    conversation.last_message_at = payload.occurred_at
    command = compliance_command(payload.body)
    consent = await _consent(db, payload.user_id, conversation.lead_id, payload.from_number)
    if command == "STOP":
        consent.status = "OPTED_OUT"
        consent.opted_out_at = datetime.now(UTC)
        conversation.status = "CONCLUDED"
        conversation.outcome = "DO_NOT_CONTACT"
        conversation.concluded_at = datetime.now(UTC)
    elif command == "START":
        consent.status = "CONSENTED"
        consent.source = "inbound_start_keyword"
        consent.recorded_at = datetime.now(UTC)
        consent.opted_out_at = None
    await db.commit()
    await publish_conversation_event(
        conversation.id,
        "message.created",
        {
            "id": message.id,
            "direction": message.direction,
            "body": message.body,
            "delivery_status": message.delivery_status,
            "occurred_at": message.occurred_at,
        },
    )
    if command is None and conversation.status == "OPEN" and consent.status == "CONSENTED":
        generate_and_send_reply.delay(str(conversation.id))
    return InternalEventResponse(
        accepted=True, duplicate=False, conversation_id=conversation.id
    )


@router.post("/events/status", response_model=InternalEventResponse)
async def delivery_status(
    payload: DeliveryStatusEvent, db: DbSession
) -> InternalEventResponse:
    if await _duplicate(
        db,
        payload.user_id,
        payload.provider,
        payload.event_id,
        "status",
        payload.raw_payload,
    ):
        return InternalEventResponse(accepted=True, duplicate=True)
    message = await db.scalar(
        select(SmsMessage).where(
            SmsMessage.user_id == payload.user_id,
            SmsMessage.provider == payload.provider,
            SmsMessage.provider_message_id == payload.provider_message_id,
        )
    )
    if message is None:
        await db.commit()
        return InternalEventResponse(accepted=True)
    message.delivery_status = payload.status
    message.provider_payload = {
        **message.provider_payload,
        **payload.raw_payload,
        "error_code": payload.error_code,
    }
    await db.commit()
    await publish_conversation_event(
        message.conversation_id,
        "message.status",
        {
            "id": message.id,
            "delivery_status": message.delivery_status,
            "error_code": payload.error_code,
        },
    )
    return InternalEventResponse(
        accepted=True, conversation_id=message.conversation_id
    )


async def _duplicate(
    db: AsyncSession,
    user_id,
    provider: str,
    event_id: str,
    event_type: str,
    raw_payload: dict,
) -> bool:
    existing = await db.scalar(
        select(SmsProviderEvent.id).where(
            SmsProviderEvent.provider == provider,
            SmsProviderEvent.event_id == event_id,
        )
    )
    if existing:
        return True
    db.add(
        SmsProviderEvent(
            user_id=user_id,
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=raw_payload,
            processed_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return False


async def _consent(db, user_id, lead_id, phone_number: str) -> SmsConsent:
    consent = await db.scalar(
        select(SmsConsent).where(
            SmsConsent.user_id == user_id,
            SmsConsent.phone_number == phone_number,
        )
    )
    if consent is None:
        consent = SmsConsent(
            user_id=user_id,
            lead_id=lead_id,
            phone_number=phone_number,
            status="UNKNOWN",
            source="inbound_message",
        )
        db.add(consent)
    return consent
