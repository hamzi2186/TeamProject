import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.config import get_settings
from app.db.session import get_db
from app.models.sms import SmsConsent, SmsConversation, SmsMessage
from app.schemas.sms import (
    BulkCampaignCreate,
    BulkCampaignResult,
    BulkCampaignSkipped,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    MockReplyRequest,
    StartConversationRequest,
)
from app.services.compliance import is_quiet_hours
from app.services.tpi_client import simulate_mock_reply
from app.workers.tasks import generate_and_send_reply

router = APIRouter(prefix="/api/v1/sms/conversations", tags=["sms-conversations"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    current: CurrentUser,
    db: DbSession,
    conversation_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[SmsConversation]:
    statement = select(SmsConversation).where(SmsConversation.user_id == current.user_id)
    if conversation_status:
        statement = statement.where(SmsConversation.status == conversation_status.upper())
    return list(
        (
            await db.scalars(
                statement.order_by(
                    SmsConversation.last_message_at.desc().nullslast(),
                    SmsConversation.created_at.desc(),
                ).limit(limit)
            )
        ).all()
    )


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate, current: CurrentUser, db: DbSession
) -> SmsConversation:
    conversation = SmsConversation(
        user_id=current.user_id,
        campaign_id=payload.campaign_id,
        lead_id=payload.lead_id,
        contact_name=payload.contact_name,
        from_number=payload.from_number,
        to_number=payload.to_number,
        timezone=payload.timezone,
        message_template=payload.message_template,
        campaign_objective=payload.campaign_objective,
        knowledge_context=payload.knowledge_context,
        max_agent_turns=payload.max_agent_turns,
    )
    consent = await db.scalar(
        select(SmsConsent).where(
            SmsConsent.user_id == current.user_id,
            SmsConsent.phone_number == payload.to_number,
        )
    )
    now = datetime.now(UTC)
    if consent is None:
        consent = SmsConsent(
            user_id=current.user_id,
            lead_id=payload.lead_id,
            phone_number=payload.to_number,
            status="CONSENTED" if payload.consented else "UNKNOWN",
            source=payload.consent_source,
            recorded_at=now if payload.consented else None,
        )
        db.add(consent)
    elif payload.consented and consent.status != "OPTED_OUT":
        consent.status = "CONSENTED"
        consent.source = payload.consent_source
        consent.recorded_at = now
    db.add(conversation)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            409, "A conversation already exists for this campaign and lead"
        ) from exc
    await db.refresh(conversation)
    return conversation


@router.post(
    "/bulk",
    response_model=BulkCampaignResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_bulk_campaign(
    payload: BulkCampaignCreate, current: CurrentUser, db: DbSession
) -> BulkCampaignResult:
    lead_ids = [lead.lead_id for lead in payload.leads]
    if len(lead_ids) != len(set(lead_ids)):
        raise HTTPException(422, "Each lead may only appear once in a bulk launch")

    existing_conversations = list(
        (
            await db.scalars(
                select(SmsConversation).where(
                    SmsConversation.user_id == current.user_id,
                    SmsConversation.campaign_id == payload.campaign_id,
                    SmsConversation.lead_id.in_(lead_ids),
                )
            )
        ).all()
    )
    existing_by_lead = {
        conversation.lead_id: conversation for conversation in existing_conversations
    }
    started_ids = set(
        (
            await db.scalars(
                select(SmsMessage.conversation_id)
                .where(
                    SmsMessage.conversation_id.in_(
                        [conversation.id for conversation in existing_conversations]
                    )
                )
                .distinct()
            )
        ).all()
    )
    phone_numbers = [lead.phone_number for lead in payload.leads]
    consents = list(
        (
            await db.scalars(
                select(SmsConsent).where(
                    SmsConsent.user_id == current.user_id,
                    SmsConsent.phone_number.in_(phone_numbers),
                )
            )
        ).all()
    )
    consent_by_phone = {consent.phone_number: consent for consent in consents}

    created: list[SmsConversation] = []
    queue_after_commit: list[SmsConversation] = []
    skipped: list[BulkCampaignSkipped] = []
    now = datetime.now(UTC)

    for lead in payload.leads:
        if not lead.consented:
            skipped.append(BulkCampaignSkipped(lead_id=lead.lead_id, reason="NO_CONSENT"))
            continue
        consent = consent_by_phone.get(lead.phone_number)
        if consent and consent.status == "OPTED_OUT":
            skipped.append(BulkCampaignSkipped(lead_id=lead.lead_id, reason="OPTED_OUT"))
            continue
        if consent is None:
            consent = SmsConsent(
                user_id=current.user_id,
                lead_id=lead.lead_id,
                phone_number=lead.phone_number,
                status="CONSENTED",
                source=lead.consent_source,
                recorded_at=now,
            )
            db.add(consent)
            consent_by_phone[lead.phone_number] = consent
        elif consent.status != "CONSENTED":
            consent.status = "CONSENTED"
            consent.source = lead.consent_source
            consent.recorded_at = now

        existing = existing_by_lead.get(lead.lead_id)
        if existing:
            if existing.id in started_ids:
                skipped.append(
                    BulkCampaignSkipped(lead_id=lead.lead_id, reason="ALREADY_STARTED")
                )
            elif existing.status != "OPEN":
                skipped.append(
                    BulkCampaignSkipped(lead_id=lead.lead_id, reason="NOT_OPEN")
                )
            elif payload.start_immediately:
                queue_after_commit.append(existing)
            continue

        conversation = SmsConversation(
            user_id=current.user_id,
            campaign_id=payload.campaign_id,
            lead_id=lead.lead_id,
            contact_name=lead.contact_name,
            from_number=payload.from_number,
            to_number=lead.phone_number,
            timezone=lead.timezone,
            message_template=payload.message_template.replace(
                "{{first_name}}", lead.first_name
            ),
            campaign_objective=payload.campaign_objective,
            knowledge_context=payload.knowledge_context,
            max_agent_turns=payload.max_agent_turns,
        )
        db.add(conversation)
        created.append(conversation)
        if payload.start_immediately:
            queue_after_commit.append(conversation)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Bulk launch conflicted with another import; retry") from exc

    for conversation in queue_after_commit:
        generate_and_send_reply.delay(str(conversation.id))

    return BulkCampaignResult(
        created=[conversation.id for conversation in created],
        queued=[conversation.id for conversation in queue_after_commit],
        skipped=skipped,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID, current: CurrentUser, db: DbSession
) -> ConversationDetail:
    conversation = await _owned_conversation(db, current.user_id, conversation_id)
    messages = list(
        (
            await db.scalars(
                select(SmsMessage)
                .where(SmsMessage.conversation_id == conversation.id)
                .order_by(SmsMessage.occurred_at.asc())
            )
        ).all()
    )
    return ConversationDetail(
        **ConversationRead.model_validate(conversation).model_dump(), messages=messages
    )


@router.post("/{conversation_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_conversation(
    conversation_id: uuid.UUID,
    payload: StartConversationRequest,
    current: CurrentUser,
    db: DbSession,
) -> dict:
    conversation = await _owned_conversation(db, current.user_id, conversation_id)
    consent = await db.scalar(
        select(SmsConsent).where(
            SmsConsent.user_id == current.user_id,
            SmsConsent.phone_number == conversation.to_number,
        )
    )
    if not consent or consent.status != "CONSENTED":
        raise HTTPException(409, "Active SMS consent is required")
    existing_message = await db.scalar(
        select(SmsMessage.id)
        .where(SmsMessage.conversation_id == conversation.id)
        .limit(1)
    )
    if existing_message:
        raise HTTPException(409, "This conversation has already started")
    settings = get_settings()
    if is_quiet_hours(
        conversation.timezone,
        start_hour=settings.quiet_hours_start,
        end_hour=settings.quiet_hours_end,
    ):
        raise HTTPException(409, "Recipient is currently inside configured quiet hours")
    generate_and_send_reply.delay(str(conversation.id))
    return {"accepted": True, "conversation_id": conversation.id}


@router.post("/{conversation_id}/mock-reply", status_code=status.HTTP_202_ACCEPTED)
async def mock_reply(
    conversation_id: uuid.UUID,
    payload: MockReplyRequest,
    current: CurrentUser,
    db: DbSession,
) -> dict:
    settings = get_settings()
    if settings.app_env == "production" or settings.sms_provider != "mock":
        raise HTTPException(404, "Mock SMS transport is not enabled")
    conversation = await _owned_conversation(db, current.user_id, conversation_id)
    if conversation.status != "OPEN":
        raise HTTPException(409, "Only open conversations accept mock replies")
    await simulate_mock_reply(
        user_id=current.user_id,
        from_number=conversation.to_number,
        to_number=conversation.from_number,
        body=payload.body,
    )
    return {"accepted": True, "conversation_id": conversation.id}


async def _owned_conversation(
    db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> SmsConversation:
    conversation = await db.scalar(
        select(SmsConversation).where(
            SmsConversation.id == conversation_id,
            SmsConversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation
