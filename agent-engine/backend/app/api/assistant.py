from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.agent import AssistantAskRequest, AssistantAskResponse
from app.services.assistant import AgentAssistantService
from app.services.tpi_client import TPIEmbeddingError, TPILlmError

router = APIRouter(
    prefix="/api/v1/agent/assistant",
    tags=["agent-assistant"],
)


@router.post("/ask", response_model=AssistantAskResponse)
async def ask_assistant(
    payload: AssistantAskRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantAskResponse:
    service = AgentAssistantService(db)
    try:
        return await service.ask(
            question=payload.question,
            top_k=payload.top_k,
            module_filter=payload.module_filter,
            similarity_threshold=payload.similarity_threshold,
        )
    except (TPILlmError, TPIEmbeddingError) as exc:
        status_code = 503 if exc.retryable else 502
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc), "retryable": exc.retryable},
        ) from exc
