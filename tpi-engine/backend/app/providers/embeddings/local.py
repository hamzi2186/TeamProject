import hashlib
import math
import re

from app.contracts.embeddings import EmbeddingResponse, EmbeddingTask

TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)


class LocalHashEmbeddingProvider:
    """Dependency-free deterministic fallback for a consistent local vector space."""

    name = "local"

    def __init__(self, *, model: str, dimension: int) -> None:
        self.model = model
        self.dimension = dimension

    async def embed(self, texts: list[str], *, task: EmbeddingTask) -> EmbeddingResponse:
        embeddings = [self._embed_one(text) for text in texts]
        return EmbeddingResponse(
            embeddings=embeddings,
            provider=self.name,
            model=self.model,
            dimension=self.dimension,
        )

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = TOKEN_RE.findall(text.casefold())
        for token in tokens:
            digest = hashlib.blake2b(token.encode(), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
