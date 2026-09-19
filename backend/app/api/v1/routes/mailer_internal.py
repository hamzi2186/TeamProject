from __future__ import annotations

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.mailer.adapters import CeleryReplyDispatcher
from app.modules.mailer.config import MailerSettings, get_mailer_settings
from app.modules.mailer.contracts import DeliveryEvent, InboundEmailEvent, ReplyDispatcher
from app.modules.mailer.repository import MailerRepository
from app.modules.mailer.schemas import InternalEventResponse
from app.modules.mailer.service import MailerResult, MailerService

logger = logging.getLogger(__name__)


def get_settings_dependency() -> MailerSettings:
    return get_mailer_settings()


def get_reply_dispatcher() -> ReplyDispatcher:
    return CeleryReplyDispatcher()


def require_internal_service(
    settings: Annotated[MailerSettings, Depends(get_settings_dependency)],
    token: Annotated[str | None, Header(alias="X-Mailer-Service-Token")] = None,
) -> None:
    """Only TPI may call these routes. With no token configured they refuse everyone."""
    expected = settings.mailer_internal_service_token
    if not expected:
        raise HTTPException(503, "Mailer internal events are not configured")
    if not token or not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, "Invalid internal service credentials")


router = APIRouter(
    prefix="/internal/mailer",
    tags=["mailer-internal"],
    dependencies=[Depends(require_internal_service)],
)

_DbSession = Annotated[AsyncSession, Depends(get_db)]
_Settings = Annotated[MailerSettings, Depends(get_settings_dependency)]


def _response(result: MailerResult, *, queued: bool = False) -> InternalEventResponse:
    return InternalEventResponse(
        accepted=result.status != "unmatched",
        status=result.status,
        duplicate=result.status == "duplicate",
        conversation_id=result.conversation_id,
        reply_queued=queued,
    )


@router.post("/events/inbound", response_model=InternalEventResponse)
async def inbound_email(
    event: InboundEmailEvent,
    db: _DbSession,
    settings: _Settings,
    dispatcher: Annotated[ReplyDispatcher, Depends(get_reply_dispatcher)],
) -> InternalEventResponse:
    """A reply that TPI has already verified and normalized.

    The reply is stored and committed first, then handed to a worker: the model call takes
    seconds, and the provider must be answered quickly. If the queue is down we answer 503
    so TPI retries, and the retry queues the reply again because it was never answered.
    """
    service = MailerService(repository=MailerRepository(db), settings=settings)
    result = await service.record_inbound_email(event)
    await db.commit()
    if result.status != "received":
        return _response(result)
    try:
        await dispatcher.enqueue_reply(
            conversation_id=result.conversation_id, inbound_email_id=result.email_id
        )
    except Exception as exc:
        logger.exception("Could not queue the reply for conversation %s", result.conversation_id)
        raise HTTPException(503, "The reply could not be queued; the email is stored, retry the event") from exc
    return _response(result, queued=True)


@router.post("/events/delivery", response_model=InternalEventResponse)
async def delivery_event(
    event: DeliveryEvent, db: _DbSession, settings: _Settings
) -> InternalEventResponse:
    """A delivery report for an email we sent, already verified and normalized by TPI."""
    service = MailerService(repository=MailerRepository(db), settings=settings)
    result = await service.handle_delivery_event(event)
    await db.commit()
    return InternalEventResponse(
        accepted=True,
        status=result.status,
        duplicate=result.status == "duplicate",
        conversation_id=result.conversation_id,
    )
