from functools import lru_cache

from app.contracts.llm import LLMGenerateResponse
from app.core.config import get_settings
from app.providers.llm.errors import LLMUnavailableError
from app.providers.llm.groq import GroqLLMProvider


class LLMService:
    def __init__(self, provider: GroqLLMProvider | None = None) -> None:
        self.provider = provider

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
        consumer: str | None = None,
    ) -> LLMGenerateResponse:
        if self.provider is None:
            raise LLMUnavailableError("LLM provider is not configured")
        return await self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    if not settings.groq_api_key:
        return LLMService(provider=None)
    provider = GroqLLMProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return LLMService(provider=provider)
