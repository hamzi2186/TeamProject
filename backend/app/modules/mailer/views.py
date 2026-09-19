from __future__ import annotations

from typing import Any
from uuid import UUID

from app.modules.mailer.outcome import html_to_text
from app.modules.mailer.repository import MailerRepository
from app.modules.mailer.schemas import (
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    EmailMessage,
    LeadSummary,
    MailerMetrics,
)


def lead_name(lead: Any) -> str | None:
    name = (lead.display_name or " ".join(filter(None, [lead.first_name, lead.last_name]))).strip()
    return name or lead.email or None


async def build_conversation_list(
    repo: MailerRepository,
    *,
    user_id: UUID,
    limit: int,
    offset: int,
    lead_id: UUID | None = None,
    campaign_id: UUID | None = None,
    status: str | None = None,
    outcome: str | None = None,
) -> ConversationList:
    filters = {"lead_id": lead_id, "campaign_id": campaign_id, "status": status, "outcome": outcome}
    conversations = await repo.list_conversations(
        user_id=user_id, limit=limit, offset=offset, **filters
    )
    total = await repo.count_conversations(user_id=user_id, **filters)
    overview = await repo.conversation_overview(
        user_id=user_id, conversation_ids=[item.id for item in conversations]
    )
    leads = await repo.get_leads(user_id=user_id, lead_ids=[item.lead_id for item in conversations])
    metrics = await repo.email_metrics(user_id=user_id)

    items = []
    for conversation in conversations:
        lead = leads.get(conversation.lead_id)
        figures = overview[conversation.id]
        items.append(
            ConversationSummary(
                id=conversation.id,
                lead_id=conversation.lead_id,
                lead_name=lead_name(lead) if lead else None,
                lead_email=lead.email if lead else None,
                campaign_id=conversation.campaign_id,
                subject=figures["first_subject"],
                status=conversation.status,
                outcome=conversation.outcome,
                turn_count=conversation.turn_count or 0,
                email_count=figures["email_count"],
                reply_count=figures["reply_count"],
                last_direction=figures["last_direction"],
                last_activity_at=figures["last_activity_at"],
                delivery_status=figures["delivery_status"],
                opened_at=conversation.opened_at,
                updated_at=conversation.updated_at,
            )
        )
    return ConversationList(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        metrics=MailerMetrics(**metrics),
    )


async def build_conversation_detail(
    repo: MailerRepository, *, user_id: UUID, conversation_id: UUID
) -> ConversationDetail | None:
    """The whole thread, or None when this tenant has no such conversation."""
    conversation = await repo.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if conversation is None:
        return None
    lead = await repo.get_lead(user_id=user_id, lead_id=conversation.lead_id)
    emails = await repo.list_emails(user_id=user_id, conversation_id=conversation.id)
    return ConversationDetail(
        id=conversation.id,
        status=conversation.status,
        outcome=conversation.outcome,
        turn_count=conversation.turn_count or 0,
        campaign_id=conversation.campaign_id,
        opened_at=conversation.opened_at,
        concluded_at=conversation.concluded_at,
        updated_at=conversation.updated_at,
        lead=(
            LeadSummary(
                id=lead.id,
                name=lead_name(lead),
                email=lead.email,
                website_url=lead.website_url,
                current_status=lead.current_status,
            )
            if lead
            else None
        ),
        emails=[
            EmailMessage(
                id=email.id,
                direction=email.direction,
                from_address=email.from_address,
                to_addresses=list(email.to_addresses or []),
                subject=email.subject,
                text_body=email.text_body
                if (email.text_body or "").strip()
                else html_to_text(email.html_body) or None,
                delivery_status=email.delivery_status,
                sent_or_received_at=email.sent_or_received_at,
            )
            for email in emails
        ],
    )
