from __future__ import annotations

import re
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.api.v1.routes.mailer_internal import router as internal_router
from app.db.session import get_db
from app.modules.mailer.repository import MailerRepository
from app.modules.mailer.schemas import ConversationDetail, ConversationList, Envelope
from app.modules.mailer.views import build_conversation_detail, build_conversation_list

router = APIRouter(prefix="/api/v1", tags=["mailer"])
router.include_router(internal_router)

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _request_id(request: Request) -> str:
    """Echo the caller's X-Request-ID when it is well formed, otherwise make one."""
    supplied = request.headers.get("X-Request-ID", "")
    return supplied if _REQUEST_ID.match(supplied) else str(uuid4())


def _not_found(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "CONVERSATION_NOT_FOUND",
                "message": "The conversation was not found.",
                "details": {},
            },
            "request_id": _request_id(request),
        },
    )


@router.get("/mailer/conversations", response_model=Envelope[ConversationList])
async def list_mailer_conversations(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: str | None = None,
    outcome: str | None = None,
    lead_id: UUID | None = None,
    campaign_id: UUID | None = None,
) -> dict[str, Any]:
    data = await build_conversation_list(
        MailerRepository(db),
        user_id=user.user_id,
        limit=limit,
        offset=offset,
        lead_id=lead_id,
        campaign_id=campaign_id,
        status=status,
        outcome=outcome,
    )
    return {"success": True, "data": data, "error": None, "request_id": _request_id(request)}


@router.get(
    "/mailer/conversations/{conversation_id}",
    response_model=Envelope[ConversationDetail],
    responses={404: {"model": Envelope[None]}},
)
async def get_mailer_conversation(
    conversation_id: UUID,
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Another tenant's conversation looks exactly like one that does not exist.
    data = await build_conversation_detail(
        MailerRepository(db), user_id=user.user_id, conversation_id=conversation_id
    )
    if data is None:
        return _not_found(request)
    return {"success": True, "data": data, "error": None, "request_id": _request_id(request)}
