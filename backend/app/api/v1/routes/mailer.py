from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["mailer"])


@router.get("/mailer/conversations")
async def list_mailer_conversations(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[object, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    _ = (user, db, limit)
    return []


@router.get("/mailer/conversations/{conversation_id}")
async def get_mailer_conversation(
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[object, Depends(get_db)],
):
    _ = (conversation_id, user, db)
    return {"conversation_id": conversation_id, "status": "WAITING_FOR_LEAD"}
