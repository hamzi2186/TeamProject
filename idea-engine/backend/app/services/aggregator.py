from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.shared_reads import (
    CallRead,
    CampaignRead,
    ConversationRead,
    EmailRead,
    LeadRead,
    SmsMessageRead,
)
from app.schemas.enums import Channel, Direction
from app.schemas.reports import TimelineEvent


async def fetch_lead_events(
    session: AsyncSession,
    lead_id: UUID,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> list[TimelineEvent]:
    """
    Fetches all call, SMS, and email interactions for a specific lead,
    normalizes them into TimelineEvent records, and returns them sorted chronologically.
    """
    events: list[TimelineEvent] = []

    # 1. Fetch Calls
    call_filters = [CallRead.lead_id == lead_id]
    if start_dt:
        call_filters.append(CallRead.started_at >= start_dt)
    if end_dt:
        call_filters.append(CallRead.started_at <= end_dt)

    call_stmt = select(CallRead).where(and_(*call_filters))
    call_res = await session.execute(call_stmt)
    for call in call_res.scalars().all():
        direction = (
            Direction.INBOUND
            if (call.direction or "").upper() == "INBOUND"
            else Direction.OUTBOUND
        )
        content_parts = []
        if call.summary:
            content_parts.append(f"Summary: {call.summary}")
        if call.transcript:
            content_parts.append(f"Transcript: {call.transcript}")
        content = "\n".join(content_parts) if content_parts else f"Call status: {call.status}"

        events.append(
            TimelineEvent(
                id=str(call.id),
                channel=Channel.CALL,
                direction=direction,
                timestamp=call.started_at,
                sender=call.from_number,
                recipient=call.to_number,
                subject=None,
                content=content,
                duration_seconds=call.duration_seconds,
                outcome=call.outcome,
                delivery_status=call.status,
            )
        )

    # 2. Fetch SMS
    sms_filters = [SmsMessageRead.lead_id == lead_id]
    if start_dt:
        sms_filters.append(SmsMessageRead.sent_or_received_at >= start_dt)
    if end_dt:
        sms_filters.append(SmsMessageRead.sent_or_received_at <= end_dt)

    sms_stmt = select(SmsMessageRead).where(and_(*sms_filters))
    sms_res = await session.execute(sms_stmt)
    for sms in sms_res.scalars().all():
        direction = (
            Direction.INBOUND
            if (sms.direction or "").upper() == "INBOUND"
            else Direction.OUTBOUND
        )
        events.append(
            TimelineEvent(
                id=str(sms.id),
                channel=Channel.SMS,
                direction=direction,
                timestamp=sms.sent_or_received_at,
                sender=sms.from_number,
                recipient=sms.to_number,
                subject=None,
                content=sms.body or "",
                duration_seconds=None,
                outcome=None,
                delivery_status=sms.delivery_status,
            )
        )

    # 3. Fetch Emails
    email_filters = [EmailRead.lead_id == lead_id]
    if start_dt:
        email_filters.append(EmailRead.sent_or_received_at >= start_dt)
    if end_dt:
        email_filters.append(EmailRead.sent_or_received_at <= end_dt)

    email_stmt = select(EmailRead).where(and_(*email_filters))
    email_res = await session.execute(email_stmt)
    for email in email_res.scalars().all():
        direction = (
            Direction.INBOUND
            if (email.direction or "").upper() == "INBOUND"
            else Direction.OUTBOUND
        )
        events.append(
            TimelineEvent(
                id=str(email.id),
                channel=Channel.EMAIL,
                direction=direction,
                timestamp=email.sent_or_received_at,
                sender=email.from_address,
                recipient=str(email.to_addresses) if email.to_addresses else None,
                subject=email.subject,
                content=email.text_body or "",
                duration_seconds=None,
                outcome=None,
                delivery_status=email.delivery_status,
            )
        )

    # Sort strictly chronologically
    events.sort(key=lambda e: e.timestamp)
    return events


async def fetch_lead_campaign_names(
    session: AsyncSession,
    lead_id: UUID,
) -> list[str]:
    """
    Best-effort campaign enrichment for a single lead.

    Campaign IDs are derived from conversation records and the calls table.
    The `campaigns` table is owned by a later platform phase, so any missing
    table (or otherwise unavailable data) degrades gracefully to an empty list.
    """
    try:
        conv_campaign_ids = (
            (
                await session.execute(
                    select(ConversationRead.campaign_id).where(
                        ConversationRead.lead_id == lead_id,
                        ConversationRead.campaign_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        call_campaign_ids = (
            (
                await session.execute(
                    select(CallRead.campaign_id).where(
                        CallRead.lead_id == lead_id,
                        CallRead.campaign_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
    except DBAPIError as exc:
        logger.debug(f"Campaign context unavailable for lead {lead_id}: {exc}")
        return []

    campaign_ids = {str(cid) for cid in [*conv_campaign_ids, *call_campaign_ids] if cid}
    if not campaign_ids:
        return []

    try:
        rows = (
            await session.execute(
                select(CampaignRead.name).where(CampaignRead.id.in_(campaign_ids))
            )
        ).scalars().all()
    except DBAPIError as exc:
        logger.debug(f"Campaign names unavailable for lead {lead_id}: {exc}")
        return []

    return sorted({name for name in rows if name})


async def get_all_leads(
    session: AsyncSession,
    user_id: UUID | None = None,
) -> list[LeadRead]:
    """
    Returns all leads registered in the shared database (optionally scoped to a user).

    The midnight report covers every lead, so unlike the previous date-based
    active-lead discovery, no activity filter is applied.
    """
    stmt = select(LeadRead)
    if user_id:
        stmt = stmt.where(LeadRead.user_id == user_id)
    stmt = stmt.order_by(LeadRead.created_at.asc())
    leads = (await session.execute(stmt)).scalars().all()
    return list(leads)