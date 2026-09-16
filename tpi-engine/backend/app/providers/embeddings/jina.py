import httpx

from app.contracts.embeddings import EmbeddingResponse, EmbeddingTask
from app.providers.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingDimensionError,
    EmbeddingRateLimitError,
    EmbeddingTemporaryError,
    EmbeddingValidationError,
    MalformedEmbeddingResponseError,
)

JINA_EMBEDDINGS_URL = "https://api.jina.ai/v1/embeddings"


class JinaEmbeddingProvider:
    name = "jina"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 30,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.dimension = dimension
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def embed(self, texts: list[str], *, task: EmbeddingTask) -> EmbeddingResponse:
        try:
            response = await self._client.post(
                JINA_EMBEDDINGS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": self.model,
                    "task": task.value,
                    "dimensions": self.dimension,
                    "input": texts,
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise EmbeddingTemporaryError("Embedding provider is temporarily unavailable") from exc
        if response.status_code in {401, 403}:
            raise EmbeddingAuthError("Embedding provider authentication failed")
        if response.status_code == 429:
            raise EmbeddingRateLimitError("Embedding provider rate limit reached")
        if response.status_code in {400, 404, 422}:
            raise EmbeddingValidationError("Embedding provider rejected the request")
        if response.status_code >= 500:
            raise EmbeddingTemporaryError("Embedding provider is temporarily unavailable")
        if response.status_code >= 400:
            raise EmbeddingValidationError("Embedding provider request failed")
        try:
            payload = response.json()
            rows = sorted(payload["data"], key=lambda row: row["index"])
            embeddings = [row["embedding"] for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedEmbeddingResponseError(
                "Embedding provider returned an invalid response"
            ) from exc
        if len(embeddings) != len(texts) or any(
            not isinstance(vector, list) for vector in embeddings
        ):
            raise MalformedEmbeddingResponseError("Embedding provider returned incomplete vectors")
        if any(len(vector) != self.dimension for vector in embeddings):
            raise EmbeddingDimensionError("Embedding provider returned an unexpected dimension")
        if any(
            not all(isinstance(value, int | float) for value in vector) for vector in embeddings
        ):
            raise MalformedEmbeddingResponseError(
                "Embedding provider returned invalid vector values"
            )
        return EmbeddingResponse(
            embeddings=embeddings,
            provider=self.name,
            model=self.model,
            dimension=self.dimension,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
