import asyncio
import uuid
from datetime import UTC, datetime

from celery.exceptions import Retry
from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.sms import SmsConsent, SmsConversation, SmsMessage
from app.services.compliance import is_quiet_hours, seconds_until_quiet_hours_end
from app.services.events import publish_conversation_event
from app.services.sms_agent import SmsAgent
from app.services.tpi_client import send_sms
from app.workers.celery_app import celery_app

_worker_loop: asyncio.AbstractEventLoop | None = None


class QuietHours(RuntimeError):
    def __init__(self, countdown: int) -> None:
        super().__init__("Message delayed until quiet hours end")
        self.countdown = countdown


def _run_async(coroutine) -> None:
    """Keep one event loop per Celery child so async DB connections remain valid."""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    _worker_loop.run_until_complete(coroutine)


async def _generate_and_send(conversation_id: uuid.UUID) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    lock = redis.lock(f"sms:conversation:{conversation_id}:agent", timeout=120)
    acquired = await lock.acquire(blocking=False)
    if not acquired:
        await redis.aclose()
        return
    try:
        await _generate_and_send_locked(conversation_id)
    finally:
        await lock.release()
        await redis.aclose()


async def _generate_and_send_locked(conversation_id: uuid.UUID) -> None:
    settings = get_settings()
    async with SessionLocal() as db:
        conversation = await db.get(SmsConversation, conversation_id)
        if not conversation or conversation.status != "OPEN":
            return
        consent = await db.scalar(
            select(SmsConsent).where(
                SmsConsent.user_id == conversation.user_id,
                SmsConsent.phone_number == conversation.to_number,
            )
        )
        if not consent or consent.status != "CONSENTED":
            return
        if conversation.agent_turn_count >= conversation.max_agent_turns:
            conversation.status = "CONCLUDED"
            conversation.outcome = "NO_RESPONSE"
            conversation.concluded_at = datetime.now(UTC)
            await db.commit()
            await publish_conversation_event(
                conversation.id, "conversation.updated", {"status": conversation.status}
            )
            return
        if is_quiet_hours(
            conversation.timezone,
            start_hour=settings.quiet_hours_start,
            end_hour=settings.quiet_hours_end,
        ):
            raise QuietHours(
                seconds_until_quiet_hours_end(
                    conversation.timezone,
                    start_hour=settings.quiet_hours_start,
                    end_hour=settings.quiet_hours_end,
                )
            )
        history = list(
            (
                await db.scalars(
                    select(SmsMessage)
                    .where(SmsMessage.conversation_id == conversation.id)
                    .order_by(SmsMessage.occurred_at.asc())
                )
            ).all()
        )
        if history and history[-1].direction != "INBOUND":
            return
        decision = await SmsAgent().decide(conversation, history)
        sent = await send_sms(
            user_id=conversation.user_id,
            to_number=conversation.to_number,
            body=decision.message,
        )
        now = datetime.now(UTC)
        message = SmsMessage(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            lead_id=conversation.lead_id,
            direction="OUTBOUND",
            from_number=sent.from_number,
            to_number=conversation.to_number,
            body=decision.message,
            provider=sent.provider,
            provider_message_id=sent.provider_message_id,
            delivery_status=sent.status,
            provider_payload={},
            occurred_at=now,
        )
        db.add(message)
        conversation.agent_turn_count += 1
        conversation.last_message_at = now
        if decision.should_stop:
            conversation.status = "CONCLUDED"
            conversation.outcome = decision.outcome
            conversation.concluded_at = now
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


@celery_app.task(bind=True, max_retries=4, name="sms.generate_and_send_reply")
def generate_and_send_reply(self, conversation_id: str) -> None:
    try:
        _run_async(_generate_and_send(uuid.UUID(conversation_id)))
    except QuietHours as exc:
        raise self.retry(exc=exc, countdown=exc.countdown) from exc
    except Retry:
        raise
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(60 * (self.request.retries + 1), 300)) from exc
