from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shared_reads import CallRead, ConversationRead, EmailRead, LeadRead, SmsMessageRead
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


async def get_active_leads_for_date(
    session: AsyncSession,
    target_date: date,
    user_id: UUID | None = None,
) -> list[LeadRead]:
    """
    Finds all leads that had outreach activity (calls, SMS, emails, or updated status)
    on the target date. If no activity is found, returns all leads registered for the user.
    """
    start_dt = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

    # Collect lead_ids with activity on this day
    active_lead_ids: set[UUID] = set()

    call_q = select(CallRead.lead_id).where(
        and_(CallRead.started_at >= start_dt, CallRead.started_at <= end_dt)
    )
    for row in (await session.execute(call_q)).scalars().all():
        active_lead_ids.add(row)

    sms_q = select(SmsMessageRead.lead_id).where(
        and_(
            SmsMessageRead.sent_or_received_at >= start_dt,
            SmsMessageRead.sent_or_received_at <= end_dt,
        )
    )
    for row in (await session.execute(sms_q)).scalars().all():
        active_lead_ids.add(row)

    email_q = select(EmailRead.lead_id).where(
        and_(
            EmailRead.sent_or_received_at >= start_dt,
            EmailRead.sent_or_received_at <= end_dt,
        )
    )
    for row in (await session.execute(email_q)).scalars().all():
        active_lead_ids.add(row)

    lead_filters = []
    if user_id:
        lead_filters.append(LeadRead.user_id == user_id)

    if active_lead_ids:
        lead_filters.append(LeadRead.id.in_(active_lead_ids))
        stmt = select(LeadRead).where(and_(*lead_filters))
        leads = (await session.execute(stmt)).scalars().all()
        return list(leads)

    # Fallback: if no touchpoints occurred specifically on that date, return all leads
    stmt = select(LeadRead)
    if lead_filters:
        stmt = stmt.where(and_(*lead_filters))
    stmt = stmt.order_by(LeadRead.created_at.desc()).limit(100)
    leads = (await session.execute(stmt)).scalars().all()
    return list(leads)
