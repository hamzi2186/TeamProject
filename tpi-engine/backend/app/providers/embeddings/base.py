from typing import Protocol

from app.contracts.embeddings import EmbeddingResponse, EmbeddingTask


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimension: int

    async def embed(self, texts: list[str], *, task: EmbeddingTask) -> EmbeddingResponse: ...
