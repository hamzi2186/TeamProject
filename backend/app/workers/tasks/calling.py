"""
Calling Engine Celery tasks (PRD §26.2).
These run asynchronously in the calling.calls queue.
"""

import asyncio
from typing import Any
from uuid import UUID

from app.core.security import AuthenticatedUser
from app.modules.calling.outcome import classify_outcome
from app.modules.calling.contracts import CallStatus
from app.tpi.voice_client import TPIVoiceClient
from app.workers.celery_app import celery_app


def _run_async(coro):
    """Helper: run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_repo(db):
    from app.modules.calling.repository import SQLCallRepository
    return SQLCallRepository(db)


@celery_app.task(name="calling.start_outbound_call", queue="calling.calls")
def start_outbound_call(
    user_id: str,
    lead_id: str,
    phone_number: str,
    purpose: str = "Follow up with lead",
    campaign_id: str | None = None,
    lead_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Dispatched by the shared campaign scheduler (PRD §17.4).
    This is the ONLY way to initiate a call — there is no customer-facing dial endpoint.
    """

    async def _run():
        from app.db.session import SessionLocal
        from app.modules.calling.service import CallingService

        request = type("OutboundCallRequest", (), {
            "lead_id": lead_id,
            "phone_number": phone_number,
            "purpose": purpose,
            "campaign_id": campaign_id,
            "prompt": None,
            "lead_variables": lead_variables or {},
        })()

        async with SessionLocal() as db:
            from app.modules.calling.repository import SQLCallRepository
            repo = SQLCallRepository(db)
            service = CallingService(provider=TPIVoiceClient(), repository=repo)
            user = AuthenticatedUser(user_id=UUID(user_id), role="system", email="")
            result = await service.start_outbound_call(user, request)
        return {"success": True, "data": result, "error": None}

    return _run_async(_run())


@celery_app.task(name="calling.process_vapi_event", queue="calling.calls")
def process_vapi_event(event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process a normalized Vapi event forwarded by TPI (PRD §17.5).
    Updates call record status, transcript, summary; triggers outcome classification.
    """

    async def _run():
        from app.db.session import SessionLocal
        from app.modules.calling.service import CallingService
        from app.modules.calling.repository import SQLCallRepository

        async with SessionLocal() as db:
            repo = SQLCallRepository(db)
            service = CallingService(provider=TPIVoiceClient(), repository=repo)
            result = await service.handle_webhook(event_id, payload)
        return result

    return _run_async(_run())


@celery_app.task(name="calling.finalize_call", queue="calling.calls")
def finalize_call(call_id: str) -> dict[str, Any]:
    """
    Finalize a call: ensure outcome is classified and persisted.
    Called after call ends if webhook has already delivered transcript.
    """

    async def _run():
        from app.db.session import SessionLocal
        from app.modules.calling.repository import SQLCallRepository
        from app.modules.calling.contracts import CallStatus
        import uuid as _uuid

        async with SessionLocal() as db:
            repo = SQLCallRepository(db)
            # Use a system user to retrieve any call by ID
            from app.modules.calling.exceptions import CallNotFoundError
            try:
                # Retrieve by scanning (no per-user restriction for system tasks)
                from sqlalchemy import select
                from app.models.calling import Call
                row = await db.get(Call, _uuid.UUID(call_id))
                if not row:
                    return {"call_id": call_id, "status": "not_found"}

                if not row.outcome and row.transcript:
                    try:
                        call_status = CallStatus(row.status)
                    except ValueError:
                        call_status = CallStatus.COMPLETED
                    outcome = classify_outcome(transcript=row.transcript, status=call_status)
                    row.outcome = outcome
                    await db.commit()

                return {"call_id": call_id, "status": "finalized", "outcome": row.outcome}
            except Exception as exc:
                return {"call_id": call_id, "status": "error", "detail": str(exc)}

    return _run_async(_run())


@celery_app.task(name="calling.classify_call_outcome", queue="calling.calls")
def classify_call_outcome(call_id: str, transcript: str, status: str) -> dict[str, Any]:
    """
    Standalone outcome classification task.
    Can be dispatched independently after transcript is available.
    """
    try:
        call_status = CallStatus(status.upper())
    except ValueError:
        call_status = CallStatus.COMPLETED
    outcome = classify_outcome(transcript=transcript, status=call_status)
    return {"call_id": call_id, "outcome": outcome, "status": "classified"}
