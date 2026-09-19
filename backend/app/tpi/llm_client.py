import httpx

from app.core.config import get_settings

LLM_TIMEOUT_SECONDS = 45


class TPILLMError(RuntimeError):
    """The TPI LLM contract could not be reached or refused the request."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class TPILLMClient:
    """Async client for the TPI text-generation contract; the vendor stays inside TPI."""

    def __init__(self, client: httpx.AsyncClient | None = None, *, consumer: str = "mailer") -> None:
        self._client = client
        self._consumer = consumer

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 900,
    ) -> str:
        settings = get_settings()
        url = f"{settings.tpi_api_base_url.rstrip('/')}/api/v1/internal/llm/generate"
        headers = {
            "X-TPI-Service-Token": settings.tpi_internal_service_token,
            "X-Consumer-Engine": self._consumer,
        }
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "consumer": self._consumer,
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    url, headers=headers, json=payload, timeout=LLM_TIMEOUT_SECONDS
                )
            else:
                async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
                    response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise TPILLMError("TPI LLM service is unavailable") from exc
        if response.status_code >= 400:
            raise TPILLMError(
                "TPI LLM service could not generate a response",
                retryable=self._retryable(response),
            )
        try:
            text = response.json()["text"]
        except (KeyError, TypeError, ValueError) as exc:
            raise TPILLMError("TPI LLM service returned an invalid response") from exc
        if not isinstance(text, str) or not text.strip():
            raise TPILLMError("TPI LLM service returned an empty response")
        return text

    @staticmethod
    def _retryable(response: httpx.Response) -> bool:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        if isinstance(detail, dict) and isinstance(detail.get("retryable"), bool):
            return detail["retryable"]
        return response.status_code == 429 or response.status_code >= 500
