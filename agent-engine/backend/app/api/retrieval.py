from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_internal_service,
)
from app.db.session import get_db
from app.schemas.agent import AgentSearchRequest, AgentSearchResponse
from app.services.retrieval import AgentRetrievalService

public_router = APIRouter(
    prefix="/api/v1/agent/retrieval",
    tags=["agent-retrieval"],
)

internal_router = APIRouter(
    prefix="/api/v1/internal/agent",
    tags=["agent-internal-retrieval"],
    dependencies=[Depends(require_internal_service)],
)


@public_router.post("/search", response_model=AgentSearchResponse)
async def search_documentation(
    payload: AgentSearchRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentSearchResponse:
    service = AgentRetrievalService(db)
    return await service.search(
        query=payload.query,
        top_k=payload.top_k,
        module_filter=payload.module_filter,
        similarity_threshold=payload.similarity_threshold,
    )


@internal_router.post("/search", response_model=AgentSearchResponse)
async def internal_search_documentation(
    payload: AgentSearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentSearchResponse:
    service = AgentRetrievalService(db)
    return await service.search(
        query=payload.query,
        top_k=payload.top_k,
        module_filter=payload.module_filter,
        similarity_threshold=payload.similarity_threshold,
    )

