from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.modules.calling.repository import SQLCallRepository
from app.modules.calling.service import CallingService
from app.tpi.voice_client import TPIVoiceClient

router = APIRouter()
webhook_router = APIRouter()


def _get_service(db: AsyncSession) -> CallingService:
    return CallingService(
        provider=TPIVoiceClient(),
        repository=SQLCallRepository(db),
    )


# ── Request / Response Schemas ──────────────────────────────────────────────

class StartCallRequest(BaseModel):
    lead_id: str
    phone_number: str = "+10000000000"
    purpose: str = "Follow up with lead"
    campaign_id: str | None = None
    prompt: str | None = None
    lead_variables: dict[str, Any] = Field(default_factory=dict)
    is_mock: bool = False


class KnowledgeSearchRequest(BaseModel):
    call_id: str | None = None
    user_id: str | None = None
    lead_id: str | None = None
    query: str = Field(min_length=1)


def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


# ── Calling Routes ───────────────────────────────────────────────────────────

@router.get("/calls")
async def list_calls(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    outcome: str | None = None,
    lead_id: str | None = None,
) -> dict[str, Any]:
    data = await _get_service(db).list_calls(
        current_user,
        status_filter=status_filter,
        outcome=outcome,
        lead_id=lead_id,
    )
    return _ok(data)


@router.post("/calls")
async def start_call(
    request: StartCallRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    return _ok(await _get_service(db).start_outbound_call(current_user, request))


@router.post("/calls/mock")
async def start_mock_call(
    request: StartCallRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    request.is_mock = True
    return _ok(await _get_service(db).start_outbound_call(current_user, request))


@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    return _ok(await _get_service(db).get_call(current_user, call_id))


@router.post("/calls/{call_id}/end")
async def end_call(
    call_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    return _ok(await _get_service(db).end_call(current_user, call_id))


@router.post("/tools/search-client-kb")
async def search_client_kb(
    request: KnowledgeSearchRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Mock KB tool contract for voice assistant (PRD §17.3 / Task §6)."""
    return _ok({
        "query": request.query,
        "call_id": request.call_id,
        "lead_id": request.lead_id,
        "results": [],
        "status": "mock_pending",
        "message": "Knowledge base pending crawler integration",
    })


# ── Webhook Routes ───────────────────────────────────────────────────────────

@webhook_router.post("/vapi/events")
async def vapi_webhook(
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_vapi_event_id: str | None = Header(default=None),
    x_tpi_event_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    Receives normalized Vapi events forwarded by TPI (PRD §17.5).
    TPI has already verified the provider signature — no Vapi HMAC check here.
    """
    return await _get_service(db).handle_webhook(x_tpi_event_id or x_vapi_event_id, payload)
