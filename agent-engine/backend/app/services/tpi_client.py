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
        default_provider: str | None = None,
        default_model: str | None = None,
        default_dimension: int | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._default_provider = default_provider
        self._default_model = default_model
        self._default_dimension = default_dimension
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
        payload: dict = {"texts": texts, "consumer": "agent"}
        self._add_space(
            payload,
            provider or self._default_provider,
            model or self._default_model,
            dimension or self._default_dimension,
        )
        return await self._request("/passages", payload, len(texts))

    async def passages_batched(
        self,
        texts: list[str],
        *,
        batch_size: int = 32,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                provider=provider or self._default_provider or "jina",
                model=model or self._default_model or "jina-embeddings-v3",
                dimension=dimension or self._default_dimension or 1024,
            )

        all_embeddings: list[list[float]] = []
        result_provider: str = ""
        result_model: str = ""
        result_dimension: int = 1024

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            res = await self.passages(batch, provider=provider, model=model, dimension=dimension)
            all_embeddings.extend(res.embeddings)
            result_provider = res.provider
            result_model = res.model
            result_dimension = res.dimension

        return EmbeddingResult(
            embeddings=all_embeddings,
            provider=result_provider,
            model=result_model,
            dimension=result_dimension,
        )

    async def query(
        self,
        text: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> EmbeddingResult:
        payload: dict = {"text": text, "consumer": "agent"}
        self._add_space(
            payload,
            provider or self._default_provider,
            model or self._default_model,
            dimension or self._default_dimension,
        )
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
                headers={
                    "X-TPI-Service-Token": self._service_token,
                    "X-Consumer-Engine": "agent",
                },
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
        default_provider=settings.embedding_provider,
        default_model=settings.embedding_model,
        default_dimension=settings.embedding_dimension,
    )


class TPILlmError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = False, code: str = "TPI_LLM_ERROR"
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass(frozen=True)
class LLMGenerationResult:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


class TPILlmClient:
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

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMGenerationResult:
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "consumer": "agent",
        }
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/internal/llm/generate",
                headers={
                    "X-TPI-Service-Token": self._service_token,
                    "X-Consumer-Engine": "agent",
                },
                json=payload,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TPILlmError("LLM generation service is unavailable", retryable=True) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {429, 502, 503, 504}
            code = "TPI_LLM_ERROR"
            message = "LLM generation service could not complete the request"
            try:
                detail = response.json().get("detail", {})
                if isinstance(detail, dict):
                    code = str(detail.get("code", code))
                    message = str(detail.get("message", message))
                    retryable = bool(detail.get("retryable", retryable))
            except (TypeError, ValueError):
                pass
            raise TPILlmError(message, retryable=retryable, code=code)

        try:
            data = response.json()
            usage = data.get("usage") or {}
            return LLMGenerationResult(
                text=data["text"],
                provider=data["provider"],
                model=data["model"],
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TPILlmError("LLM generation service returned an invalid response") from exc

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def create_tpi_llm_client() -> TPILlmClient:
    settings = get_settings()
    return TPILlmClient(
        base_url=settings.tpi_api_base_url,
        service_token=settings.tpi_internal_service_token,
    )

