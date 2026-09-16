from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_embedding_client
from app.auth.dependencies import AuthenticatedUser, get_current_user, require_internal_service
from app.schemas.scraper import InternalSearchRequest, SearchRequest, SearchResponse
from app.services.retrieval import (
    KnowledgeBaseNotReadyError,
    RetrievalDimensionError,
    RetrievalService,
)
from app.services.tpi_embeddings import TPIEmbeddingClient, TPIEmbeddingError

router = APIRouter(prefix="/api/v1", tags=["client-kb-retrieval"])
internal_router = APIRouter(
    prefix="/api/v1/internal/client-kb",
    tags=["internal-client-kb"],
    dependencies=[Depends(require_internal_service)],
)


async def execute_search(
    *,
    db: AsyncSession,
    embeddings: TPIEmbeddingClient,
    user_id: UUID,
    knowledge_base_id: UUID,
    request: SearchRequest,
) -> SearchResponse:
    try:
        return await RetrievalService(db, embeddings).search(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            top_k=request.top_k,
            minimum_similarity=request.minimum_similarity,
        )
    except LookupError as exc:
        raise HTTPException(404, "Knowledge base not found") from exc
    except KnowledgeBaseNotReadyError as exc:
        raise HTTPException(409, "Knowledge base is not ready") from exc
    except RetrievalDimensionError as exc:
        raise HTTPException(409, "Knowledge base embedding configuration is incompatible") from exc
    except TPIEmbeddingError as exc:
        status = 503 if exc.retryable else 502
        raise HTTPException(status, "Query embedding could not be generated") from exc


@router.post(
    "/knowledge-bases/{knowledge_base_id}/search",
    response_model=SearchResponse,
)
async def search_knowledge_base(
    knowledge_base_id: UUID,
    payload: SearchRequest,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    embeddings: Annotated[TPIEmbeddingClient, Depends(get_embedding_client)],
) -> SearchResponse:
    return await execute_search(
        db=db,
        embeddings=embeddings,
        user_id=current.user_id,
        knowledge_base_id=knowledge_base_id,
        request=payload,
    )


@internal_router.post("/search", response_model=SearchResponse)
async def internal_search(
    payload: InternalSearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    embeddings: Annotated[TPIEmbeddingClient, Depends(get_embedding_client)],
) -> SearchResponse:
    return await execute_search(
        db=db,
        embeddings=embeddings,
        user_id=payload.user_id,
        knowledge_base_id=payload.knowledge_base_id,
        request=payload,
    )
