from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, case, func, or_, select, text, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calling import SeenWebhookEvent
from app.models.lead import Lead
from app.models.mailer import EMAIL_CHANNEL, Email, EmailConversation, LeadStatusHistory
from app.modules.mailer.contracts import EmailDirection
from app.modules.mailer.exceptions import MailerTenantError, MailerValidationError
from app.modules.mailer.thread import normalize_message_id

_STATUS_SOURCES = {"AI", "SYSTEM", "USER"}
_DELIVERY_RANK = {"queued": 0, "sent": 1, "delayed": 1, "delivered": 2}
_DELIVERY_FAILURES = {"bounced", "failed", "complained"}


def should_apply_delivery_status(current: str | None, new: str | None) -> bool:
    """Decide whether a delivery event should overwrite the stored status.

    Providers retry and deliver events out of order, so a late `sent` must not undo `delivered`,
    and a bounce is final.
    """
    new = (new or "").strip().lower()
    if new not in _DELIVERY_RANK and new not in _DELIVERY_FAILURES:
        return False
    current = (current or "").strip().lower()
    if current not in _DELIVERY_RANK and current not in _DELIVERY_FAILURES:
        return True
    if current in _DELIVERY_FAILURES:
        return False
    if new in _DELIVERY_FAILURES:
        return True
    return _DELIVERY_RANK[new] > _DELIVERY_RANK[current]


def _webhook_event_insert(dialect_name: str, *, event_id: str, source: str):
    if dialect_name == "postgresql":
        insert = postgresql.insert
    elif dialect_name == "sqlite":
        insert = sqlite.insert
    else:
        raise NotImplementedError(f"unsupported database dialect: {dialect_name}")
    return (
        insert(SeenWebhookEvent)
        .values(event_id=event_id, source=source)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )


class MailerRepository:
    """Persistence for the Mailer Engine.

    Methods flush but never commit. The caller owns the transaction, so an idempotency marker and
    the writes it guards commit or roll back together, and a failed event can be retried.

    Methods that take `user_id` are tenant-scoped. `get_conversation_by_verified_id`,
    `find_correlation_candidates` and `update_delivery_status` are the exceptions: they serve
    provider events, which carry no tenant, and resolve it from the row they match. Only pass
    them identifiers that were authenticated or that match messages we stored ourselves.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    # -- conversations -------------------------------------------------------------------

    async def open_conversation(
        self,
        *,
        user_id: UUID,
        lead_id: UUID,
        campaign_id: UUID | None = None,
        status: str = "OPEN",
    ) -> tuple[EmailConversation, bool]:
        """Return the email conversation for this lead and campaign, creating it if needed.

        The table has no uniqueness rule, so concurrent workers could otherwise both create one.
        A transaction-scoped advisory lock serializes them; commit promptly to release it.
        """
        await self._advisory_lock(f"mailer:conversation:{user_id}:{lead_id}:{campaign_id}")
        existing = await self._db.scalar(
            select(EmailConversation)
            .where(
                *self._email_scope(user_id),
                EmailConversation.lead_id == lead_id,
                EmailConversation.campaign_id == campaign_id,  # None compiles to IS NULL
            )
            .order_by(EmailConversation.created_at.asc(), EmailConversation.id.asc())
            .limit(1)
        )
        if existing is not None:
            return existing, False
        conversation = EmailConversation(
            id=uuid4(),
            user_id=user_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            channel=EMAIL_CHANNEL,
            status=status,
            turn_count=0,
        )
        self._db.add(conversation)
        await self._db.flush()
        return conversation, True

    async def get_conversation(
        self, *, user_id: UUID, conversation_id: UUID
    ) -> EmailConversation | None:
        return await self._db.scalar(
            select(EmailConversation).where(
                *self._email_scope(user_id), EmailConversation.id == conversation_id
            )
        )

    async def get_conversation_by_verified_id(
        self, conversation_id: UUID
    ) -> EmailConversation | None:
        """Look a conversation up without a tenant filter.

        Only call this with an id that was authenticated, such as one recovered from a signed
        Reply-To token. The tenant is then whatever the row says.
        """
        return await self._db.scalar(
            select(EmailConversation).where(
                EmailConversation.id == conversation_id,
                EmailConversation.channel == EMAIL_CHANNEL,
            )
        )

    def _conversation_filters(
        self,
        user_id: UUID,
        lead_id: UUID | None,
        campaign_id: UUID | None,
        status: str | None,
        outcome: str | None,
    ) -> list[Any]:
        conditions = list(self._email_scope(user_id))
        if lead_id is not None:
            conditions.append(EmailConversation.lead_id == lead_id)
        if campaign_id is not None:
            conditions.append(EmailConversation.campaign_id == campaign_id)
        if status is not None:
            conditions.append(EmailConversation.status == status)
        if outcome is not None:
            conditions.append(EmailConversation.outcome == outcome)
        return conditions

    async def list_conversations(
        self,
        *,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        lead_id: UUID | None = None,
        campaign_id: UUID | None = None,
        status: str | None = None,
        outcome: str | None = None,
    ) -> list[EmailConversation]:
        stmt = (
            select(EmailConversation)
            .where(*self._conversation_filters(user_id, lead_id, campaign_id, status, outcome))
            .order_by(EmailConversation.updated_at.desc().nulls_last(), EmailConversation.id.desc())
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        )
        return list((await self._db.scalars(stmt)).all())

    async def count_conversations(
        self,
        *,
        user_id: UUID,
        lead_id: UUID | None = None,
        campaign_id: UUID | None = None,
        status: str | None = None,
        outcome: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(EmailConversation)
            .where(*self._conversation_filters(user_id, lead_id, campaign_id, status, outcome))
        )
        return int(await self._db.scalar(stmt) or 0)

    async def conversation_overview(
        self, *, user_id: UUID, conversation_ids: Sequence[UUID]
    ) -> dict[UUID, dict[str, Any]]:
        """Figures for a page of conversations, gathered in two queries instead of two per row."""
        ids = list(conversation_ids)
        overview: dict[UUID, dict[str, Any]] = {
            conversation_id: {
                "email_count": 0,
                "reply_count": 0,
                "first_subject": None,
                "last_direction": None,
                "last_activity_at": None,
                "delivery_status": None,
            }
            for conversation_id in ids
        }
        if not ids:
            return overview
        counts = await self._db.execute(
            select(Email.conversation_id, Email.direction, func.count())
            .where(Email.user_id == user_id, Email.conversation_id.in_(ids))
            .group_by(Email.conversation_id, Email.direction)
        )
        for conversation_id, direction, number in counts:
            overview[conversation_id]["email_count"] += number
            if direction == EmailDirection.INBOUND.value:
                overview[conversation_id]["reply_count"] += number

        newest = (Email.sent_or_received_at.desc(), Email.created_at.desc(), Email.id.desc())
        oldest = (Email.sent_or_received_at.asc(), Email.created_at.asc(), Email.id.asc())
        ranked = (
            select(
                Email.conversation_id.label("conversation_id"),
                Email.direction.label("direction"),
                Email.subject.label("subject"),
                Email.delivery_status.label("delivery_status"),
                Email.sent_or_received_at.label("moment"),
                func.row_number().over(partition_by=Email.conversation_id, order_by=newest).label("newest"),
                func.row_number().over(partition_by=Email.conversation_id, order_by=oldest).label("oldest"),
                func.row_number()
                .over(partition_by=(Email.conversation_id, Email.direction), order_by=newest)
                .label("newest_in_direction"),
            )
            .where(Email.user_id == user_id, Email.conversation_id.in_(ids))
            .subquery()
        )
        rows = await self._db.execute(
            select(ranked).where(
                or_(
                    ranked.c.newest == 1,
                    ranked.c.oldest == 1,
                    and_(
                        ranked.c.direction == EmailDirection.OUTBOUND.value,
                        ranked.c.newest_in_direction == 1,
                    ),
                )
            )
        )
        for row in rows:
            entry = overview[row.conversation_id]
            if row.newest == 1:
                entry["last_direction"] = row.direction
                entry["last_activity_at"] = row.moment
            if row.oldest == 1:
                entry["first_subject"] = row.subject
            if row.direction == EmailDirection.OUTBOUND.value and row.newest_in_direction == 1:
                entry["delivery_status"] = row.delivery_status
        return overview

    async def email_metrics(self, *, user_id: UUID) -> dict[str, int]:
        """Headline counts for the Mailer page (Master PRD 32.31)."""
        outbound = Email.direction == EmailDirection.OUTBOUND.value

        def count_if(condition: Any):
            return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

        row = (
            await self._db.execute(
                select(
                    count_if(outbound),
                    count_if(and_(outbound, Email.delivery_status == "delivered")),
                    count_if(Email.direction == EmailDirection.INBOUND.value),
                    count_if(and_(outbound, Email.delivery_status.in_(tuple(_DELIVERY_FAILURES)))),
                ).where(Email.user_id == user_id)
            )
        ).one()
        interested = await self.count_conversations(user_id=user_id, outcome="INTERESTED")
        total = await self.count_conversations(user_id=user_id)
        return {
            "conversations": total,
            "emails_sent": int(row[0]),
            "delivered": int(row[1]),
            "replies": int(row[2]),
            "bounced": int(row[3]),
            "interested": interested,
        }

    async def update_conversation(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        status: str | None = None,
        outcome: str | None = None,
        provider_thread_id: str | None = None,
        add_turn: bool = False,
        conclude: bool = False,
    ) -> EmailConversation | None:
        """Update a conversation and return it, or None if this tenant does not own it.

        The turn counter is incremented in SQL, so two workers cannot lose an increment.
        """
        values: dict[str, Any] = {}
        if status is not None:
            values["status"] = status
        if outcome is not None:
            values["outcome"] = outcome
        if provider_thread_id is not None:
            values["provider_thread_id"] = provider_thread_id
        if add_turn:
            values["turn_count"] = func.coalesce(EmailConversation.turn_count, 0) + 1
        if conclude:
            values["concluded_at"] = datetime.now(UTC)
        if not values:
            return await self.get_conversation(user_id=user_id, conversation_id=conversation_id)
        values["updated_at"] = datetime.now(UTC)
        result = await self._db.execute(
            update(EmailConversation)
            .where(*self._email_scope(user_id), EmailConversation.id == conversation_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount == 0:
            return None
        return await self._db.scalar(
            select(EmailConversation)
            .where(EmailConversation.id == conversation_id)
            .execution_options(populate_existing=True)
        )

    # -- emails --------------------------------------------------------------------------

    async def add_email(
        self,
        *,
        conversation_id: UUID,
        user_id: UUID,
        lead_id: UUID,
        direction: EmailDirection | str,
        from_address: str | None = None,
        to_addresses: Sequence[str] | None = None,
        subject: str | None = None,
        text_body: str | None = None,
        html_body: str | None = None,
        provider: str | None = None,
        provider_email_id: str | None = None,
        internet_message_id: str | None = None,
        in_reply_to: str | None = None,
        references_header: str | None = None,
        delivery_status: str | None = None,
        provider_payload: dict[str, Any] | None = None,
        sent_or_received_at: datetime | None = None,
    ) -> tuple[Email, bool]:
        """Store an email on a conversation the tenant owns.

        Returns `(email, created)`. An email the provider already gave us an id for is returned
        as is rather than stored twice, so a retried task cannot duplicate a message.
        """
        try:
            direction = EmailDirection(direction)
        except ValueError as exc:
            raise MailerValidationError(f"unknown email direction: {direction!r}") from exc
        conversation = await self.get_conversation(user_id=user_id, conversation_id=conversation_id)
        if conversation is None:
            raise MailerTenantError("Conversation is not owned by this tenant")
        if conversation.lead_id != lead_id:
            raise MailerValidationError("lead_id does not match the conversation")
        if provider_email_id:
            existing = await self._db.scalar(
                select(Email).where(
                    Email.user_id == user_id,
                    Email.provider == provider,
                    Email.provider_email_id == provider_email_id,
                )
            )
            if existing is not None:
                return existing, False
        email = Email(
            id=uuid4(),
            conversation_id=conversation_id,
            user_id=user_id,
            lead_id=lead_id,
            direction=direction.value,
            from_address=from_address,
            to_addresses=list(to_addresses or []),
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            provider=provider,
            provider_email_id=provider_email_id,
            internet_message_id=internet_message_id,
            in_reply_to=in_reply_to,
            references_header=references_header,
            delivery_status=delivery_status,
            provider_payload=dict(provider_payload or {}),
            sent_or_received_at=sent_or_received_at or datetime.now(UTC),
        )
        self._db.add(email)
        await self._db.flush()
        await self._db.execute(
            update(EmailConversation)
            .where(EmailConversation.id == conversation_id)
            .values(updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        return email, True

    async def list_emails(
        self, *, user_id: UUID, conversation_id: UUID, limit: int | None = None
    ) -> list[Email]:
        stmt = (
            select(Email)
            .where(Email.user_id == user_id, Email.conversation_id == conversation_id)
            .order_by(Email.sent_or_received_at.asc(), Email.created_at.asc(), Email.id.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list((await self._db.scalars(stmt)).all())

    async def list_recent_emails(
        self, *, user_id: UUID, conversation_id: UUID, limit: int = 10
    ) -> list[Email]:
        """The last `limit` emails of a thread, oldest first, for building an AI prompt."""
        stmt = (
            select(Email)
            .where(Email.user_id == user_id, Email.conversation_id == conversation_id)
            .order_by(Email.sent_or_received_at.desc(), Email.created_at.desc(), Email.id.desc())
            .limit(max(1, limit))
        )
        return list(reversed((await self._db.scalars(stmt)).all()))

    async def find_correlation_candidates(
        self, *, message_ids: Sequence[str], provider_email_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Stored emails an inbound reply might belong to, shaped for `correlate_email`.

        Matches on the Message-IDs from the reply's In-Reply-To and References headers, in
        either bracketed or bare form, and on a provider id. No tenant filter: an inbound reply
        does not say whose it is, so the tenant is taken from the matched email.
        """
        variants: set[str] = set()
        for message_id in message_ids:
            normalized = normalize_message_id(message_id)
            if normalized:
                variants.update({normalized, f"<{normalized}>"})
        conditions = []
        if variants:
            conditions.append(Email.internet_message_id.in_(variants))
        if provider_email_id:
            conditions.append(Email.provider_email_id == provider_email_id)
        if not conditions:
            return []
        stmt = (
            select(Email)
            .join(EmailConversation, EmailConversation.id == Email.conversation_id)
            .where(EmailConversation.channel == EMAIL_CHANNEL, or_(*conditions))
            .order_by(Email.sent_or_received_at.desc())
            .limit(50)
        )
        return [
            {
                "conversation_id": str(email.conversation_id),
                "user_id": email.user_id,
                "lead_id": email.lead_id,
                "direction": email.direction,
                "internet_message_id": email.internet_message_id,
                "provider_email_id": email.provider_email_id,
            }
            for email in (await self._db.scalars(stmt)).all()
        ]

    async def update_delivery_status(
        self, *, provider: str, provider_email_id: str, delivery_status: str
    ) -> Email | None:
        """Apply a provider delivery event to the outbound email it refers to.

        Returns the email, or None when we never sent one with that id. An event for an unknown
        email is not an error: providers also report on mail sent outside this engine.
        """
        if not provider_email_id:
            return None
        email = await self._db.scalar(
            select(Email).where(
                Email.provider == provider,
                Email.provider_email_id == provider_email_id,
                Email.direction == EmailDirection.OUTBOUND.value,
            )
        )
        if email is None:
            return None
        new_status = (delivery_status or "").strip().lower()
        if should_apply_delivery_status(email.delivery_status, new_status):
            email.delivery_status = new_status
            await self._db.flush()
        return email

    async def get_email(self, *, user_id: UUID, email_id: UUID) -> Email | None:
        return await self._db.scalar(
            select(Email).where(Email.user_id == user_id, Email.id == email_id)
        )

    async def find_email_by_provider_id(
        self,
        *,
        user_id: UUID,
        provider: str,
        provider_email_id: str | None,
        direction: EmailDirection | str,
    ) -> Email | None:
        if not provider_email_id:
            return None
        return await self._db.scalar(
            select(Email).where(
                Email.user_id == user_id,
                Email.provider == provider,
                Email.provider_email_id == provider_email_id,
                Email.direction == EmailDirection(direction).value,
            )
        )

    # -- idempotency ---------------------------------------------------------------------

    async def record_webhook_event(self, *, provider: str, provider_event_id: str) -> bool:
        """Record that an event was seen. Returns False if it had been seen before.

        Uses `INSERT ... ON CONFLICT DO NOTHING`, so two workers racing on the same event cannot
        both win. The id is prefixed with the provider so it cannot collide with another
        engine's ids in the shared `seen_webhook_events` table.
        """
        provider = (provider or "").strip().lower()
        event_id = (provider_event_id or "").strip()
        if not provider or not event_id:
            raise MailerValidationError("provider and provider_event_id are required")
        result = await self._db.execute(
            _webhook_event_insert(
                self._dialect_name(), event_id=f"{provider}:{event_id}", source=provider[:32]
            )
        )
        return result.rowcount == 1

    # -- leads ---------------------------------------------------------------------------

    async def get_lead(self, *, user_id: UUID, lead_id: UUID) -> Lead | None:
        return await self._db.scalar(
            select(Lead).where(Lead.user_id == user_id, Lead.id == lead_id)
        )

    async def get_leads(self, *, user_id: UUID, lead_ids: Sequence[UUID]) -> dict[UUID, Lead]:
        ids = list(set(lead_ids))
        if not ids:
            return {}
        rows = await self._db.scalars(select(Lead).where(Lead.user_id == user_id, Lead.id.in_(ids)))
        return {lead.id: lead for lead in rows.all()}

    async def record_status_change(
        self,
        *,
        user_id: UUID,
        lead_id: UUID,
        new_status: str,
        source: str,
        previous_status: str | None = None,
        campaign_id: UUID | None = None,
        reason: str | None = None,
    ) -> LeadStatusHistory:
        if source not in _STATUS_SOURCES:
            raise MailerValidationError(f"source must be one of {sorted(_STATUS_SOURCES)}")
        if await self.get_lead(user_id=user_id, lead_id=lead_id) is None:
            raise MailerTenantError("Lead is not owned by this tenant")
        row = LeadStatusHistory(
            id=uuid4(),
            user_id=user_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            source=source,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    # -- internals -----------------------------------------------------------------------

    @staticmethod
    def _email_scope(user_id: UUID) -> tuple[Any, Any]:
        return (EmailConversation.user_id == user_id, EmailConversation.channel == EMAIL_CHANNEL)

    def _dialect_name(self) -> str:
        return self._db.get_bind().dialect.name

    async def _advisory_lock(self, key: str) -> None:
        if self._dialect_name() != "postgresql":
            return
        await self._db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )
