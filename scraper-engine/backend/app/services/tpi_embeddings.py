from dataclasses import dataclass

import httpx

from app.core.config import get_settings


class TPIEmbeddingError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, code: str = "TPI_ERROR") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass(frozen=True)
class EmbeddingResult:
    embeddings: list[list[float]]
    provider: str
    model: str
    dimension: int


class TPIEmbeddingClient:
    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=45, trust_env=False)

    async def passages(
        self,
        texts: list[str],
        *,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> EmbeddingResult:
        payload: dict = {"texts": texts}
        self._add_space(payload, provider, model, dimension)
        return await self._request("/passages", payload, len(texts))

    async def query(
        self, text: str, *, provider: str, model: str, dimension: int
    ) -> EmbeddingResult:
        payload = {
            "text": text,
            "provider": provider,
            "model": model,
            "dimension": dimension,
        }
        return await self._request("/query", payload, 1)

    @staticmethod
    def _add_space(
        payload: dict, provider: str | None, model: str | None, dimension: int | None
    ) -> None:
        if provider is not None:
            payload["provider"] = provider
        if model is not None:
            payload["model"] = model
        if dimension is not None:
            payload["dimension"] = dimension

    async def _request(self, path: str, payload: dict, expected_count: int) -> EmbeddingResult:
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/internal/embeddings{path}",
                headers={"X-TPI-Service-Token": self._service_token},
                json=payload,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TPIEmbeddingError("Embedding service is unavailable", retryable=True) from exc
        if response.status_code >= 400:
            retryable = response.status_code in {429, 502, 503, 504}
            code = "TPI_EMBEDDING_ERROR"
            try:
                detail = response.json().get("detail", {})
                if isinstance(detail, dict):
                    code = str(detail.get("code", code))
                    retryable = bool(detail.get("retryable", retryable))
            except (TypeError, ValueError):
                pass
            raise TPIEmbeddingError(
                "Embedding service could not complete the request",
                retryable=retryable,
                code=code,
            )
        try:
            data = response.json()
            result = EmbeddingResult(
                embeddings=data["embeddings"],
                provider=data["provider"],
                model=data["model"],
                dimension=data["dimension"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TPIEmbeddingError("Embedding service returned an invalid response") from exc
        if len(result.embeddings) != expected_count or any(
            len(vector) != result.dimension for vector in result.embeddings
        ):
            raise TPIEmbeddingError("Embedding service returned incompatible vectors")
        return result

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def create_tpi_embedding_client() -> TPIEmbeddingClient:
    settings = get_settings()
    return TPIEmbeddingClient(
        base_url=settings.tpi_api_base_url,
        service_token=settings.tpi_internal_service_token,
    )
