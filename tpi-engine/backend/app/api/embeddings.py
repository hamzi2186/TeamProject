from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.dependencies import require_service_token
from app.contracts.embeddings import (
    EmbeddingResponse,
    PassageEmbeddingRequest,
    QueryEmbeddingRequest,
)
from app.providers.embeddings.errors import EmbeddingError
from app.providers.embeddings.service import EmbeddingService, get_embedding_service

router = APIRouter(
    prefix="/api/v1/internal/embeddings",
    tags=["internal-embeddings"],
    dependencies=[Depends(require_service_token)],
)


def normalized_error(error: EmbeddingError) -> HTTPException:
    return HTTPException(
        status_code=error.http_status,
        detail={"code": error.code, "message": str(error), "retryable": error.retryable},
    )


@router.post("/passages", response_model=EmbeddingResponse)
async def embed_passages(
    payload: PassageEmbeddingRequest,
    service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    x_consumer_engine: Annotated[str | None, Header(alias="X-Consumer-Engine")] = None,
) -> EmbeddingResponse:
    try:
        return await service.passages(
            payload.texts,
            provider=payload.provider,
            model=payload.model,
            dimension=payload.dimension,
            consumer=payload.consumer or x_consumer_engine,
        )
    except EmbeddingError as exc:
        raise normalized_error(exc) from exc


@router.post("/query", response_model=EmbeddingResponse)
async def embed_query(
    payload: QueryEmbeddingRequest,
    service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    x_consumer_engine: Annotated[str | None, Header(alias="X-Consumer-Engine")] = None,
) -> EmbeddingResponse:
    try:
        return await service.query(
            payload.text,
            provider=payload.provider,
            model=payload.model,
            dimension=payload.dimension,
            consumer=payload.consumer or x_consumer_engine,
        )
    except EmbeddingError as exc:
        raise normalized_error(exc) from exc
