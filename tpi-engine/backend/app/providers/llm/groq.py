import httpx

from app.contracts.llm import LLMGenerateResponse, LLMUsage
from app.providers.llm.errors import (
    LLMAuthError,
    LLMRateLimitError,
    LLMTemporaryError,
    LLMValidationError,
    MalformedLLMResponseError,
)

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLLMProvider:
    name = "groq"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMGenerateResponse:
        try:
            response = await self._client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LLMTemporaryError("LLM provider is temporarily unavailable") from exc

        if response.status_code in {401, 403}:
            raise LLMAuthError("LLM provider authentication failed")
        if response.status_code == 429:
            raise LLMRateLimitError("LLM provider rate limit reached")
        if response.status_code in {400, 404, 422}:
            raise LLMValidationError("LLM provider rejected the request")
        if response.status_code >= 500:
            raise LLMTemporaryError("LLM provider is temporarily unavailable")
        if response.status_code >= 400:
            raise LLMValidationError("LLM provider request failed")

        try:
            payload = response.json()
            choices = payload["choices"]
            first_choice = choices[0]
            text = first_choice["message"]["content"]
            usage_data = payload.get("usage") or {}
            input_tokens = int(usage_data.get("prompt_tokens", 0) or 0)
            output_tokens = int(usage_data.get("completion_tokens", 0) or 0)
            returned_model = payload.get("model") or self.model
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MalformedLLMResponseError("LLM provider returned an invalid response") from exc

        if not isinstance(text, str):
            raise MalformedLLMResponseError("LLM provider returned non-text completion")

        return LLMGenerateResponse(
            text=text,
            provider=self.name,
            model=returned_model,
            usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
