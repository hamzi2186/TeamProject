from functools import lru_cache

from app.contracts.embeddings import EmbeddingResponse, EmbeddingTask
from app.core.config import get_settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.errors import (
    EmbeddingError,
    EmbeddingUnavailableError,
    EmbeddingValidationError,
)
from app.providers.embeddings.jina import JinaEmbeddingProvider
from app.providers.embeddings.local import LocalHashEmbeddingProvider


class EmbeddingService:
    def __init__(
        self,
        providers: dict[str, EmbeddingProvider],
        *,
        primary: str,
        fallback: str | None,
    ) -> None:
        self._providers = providers
        self._primary = primary
        self._fallback = fallback

    async def passages(
        self,
        texts: list[str],
        *,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> EmbeddingResponse:
        return await self._embed(
            texts,
            task=EmbeddingTask.PASSAGE,
            provider=provider,
            model=model,
            dimension=dimension,
        )

    async def query(
        self,
        text: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> EmbeddingResponse:
        return await self._embed(
            [text],
            task=EmbeddingTask.QUERY,
            provider=provider,
            model=model,
            dimension=dimension,
        )

    async def _embed(
        self,
        texts: list[str],
        *,
        task: EmbeddingTask,
        provider: str | None,
        model: str | None,
        dimension: int | None,
    ) -> EmbeddingResponse:
        selected_name = (provider or self._primary).casefold()
        selected = self._providers.get(selected_name)
        if selected is None:
            if provider or not self._fallback:
                raise EmbeddingUnavailableError("Requested embedding provider is unavailable")
            selected_name = self._fallback
            selected = self._providers.get(selected_name)
            if selected is None:
                raise EmbeddingUnavailableError("Requested embedding provider is unavailable")
        self._validate_space(selected, model=model, dimension=dimension)
        try:
            return await selected.embed(texts, task=task)
        except EmbeddingError:
            if provider or not self._fallback or self._fallback == selected_name:
                raise
            fallback = self._providers.get(self._fallback)
            if fallback is None:
                raise
            return await fallback.embed(texts, task=task)

    @staticmethod
    def _validate_space(
        provider: EmbeddingProvider, *, model: str | None, dimension: int | None
    ) -> None:
        if model is not None and model != provider.model:
            raise EmbeddingValidationError("Requested embedding model is unavailable")
        if dimension is not None and dimension != provider.dimension:
            raise EmbeddingValidationError("Requested embedding dimension is unavailable")


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    providers: dict[str, EmbeddingProvider] = {
        "local": LocalHashEmbeddingProvider(
            model=settings.local_embedding_model,
            dimension=settings.local_embedding_dimension,
        )
    }
    if settings.jina_api_key:
        providers["jina"] = JinaEmbeddingProvider(
            api_key=settings.jina_api_key,
            model=settings.jina_embedding_model,
            dimension=settings.jina_embedding_dimension,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    return EmbeddingService(
        providers,
        primary=settings.embedding_provider,
        fallback=settings.embedding_fallback_provider,
    )
