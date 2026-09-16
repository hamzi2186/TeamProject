import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.llm.errors import (
    LLMAuthError,
    LLMRateLimitError,
    LLMTemporaryError,
    LLMValidationError,
    MalformedLLMResponseError,
)
from app.providers.llm.groq import GROQ_CHAT_COMPLETIONS_URL, GroqLLMProvider
from app.providers.llm.service import LLMService, get_llm_service


def groq_provider(handler, *, model: str = "llama-3.3-70b-versatile") -> GroqLLMProvider:
    return GroqLLMProvider(
        api_key="secret-groq-key-123",
        model=model,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_groq_successful_generation_and_normalization():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == GROQ_CHAT_COMPLETIONS_URL
        assert request.headers["authorization"] == "Bearer secret-groq-key-123"
        body = json.loads(request.content)
        assert body["model"] == "llama-3.3-70b-versatile"
        assert body["messages"] == [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain T Rex."},
        ]
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 800
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "llama-3.3-70b-versatile",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "T Rex is an autonomous outreach platform.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 25,
                    "completion_tokens": 10,
                    "total_tokens": 35,
                },
            },
        )

    provider = groq_provider(handler)
    res = await provider.generate(
        system_prompt="You are a helpful assistant.",
        user_prompt="Explain T Rex.",
        temperature=0.2,
        max_tokens=800,
    )
    assert res.text == "T Rex is an autonomous outreach platform."
    assert res.provider == "groq"
    assert res.model == "llama-3.3-70b-versatile"
    assert res.usage.input_tokens == 25
    assert res.usage.output_tokens == 10


@pytest.mark.asyncio
async def test_groq_error_mappings():
    # 1. 401 -> LLMAuthError
    def auth_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    p = groq_provider(auth_handler)
    with pytest.raises(LLMAuthError) as exc_info:
        await p.generate(system_prompt="s", user_prompt="u")
    assert "secret-groq-key-123" not in str(exc_info.value)

    # 2. 429 -> LLMRateLimitError
    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})

    p = groq_provider(rate_limit_handler)
    with pytest.raises(LLMRateLimitError):
        await p.generate(system_prompt="s", user_prompt="u")

    # 3. 400 -> LLMValidationError
    def validation_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Invalid prompt"}})

    p = groq_provider(validation_handler)
    with pytest.raises(LLMValidationError):
        await p.generate(system_prompt="s", user_prompt="u")

    # 4. 500 -> LLMTemporaryError
    def server_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    p = groq_provider(server_handler)
    with pytest.raises(LLMTemporaryError):
        await p.generate(system_prompt="s", user_prompt="u")

    # 5. Malformed payload
    def malformed_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    p = groq_provider(malformed_handler)
    with pytest.raises(MalformedLLMResponseError):
        await p.generate(system_prompt="s", user_prompt="u")


@pytest.mark.asyncio
async def test_groq_timeout_mapping():
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out")

    p = groq_provider(timeout_handler)
    with pytest.raises(LLMTemporaryError):
        await p.generate(system_prompt="s", user_prompt="u")


def test_endpoint_missing_service_token_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/v1/internal/llm/generate",
        json={"system_prompt": "sys", "user_prompt": "usr"},
    )
    # FastAPI returns 422 for missing required header
    assert response.status_code == 422


def test_endpoint_invalid_service_token_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/v1/internal/llm/generate",
        headers={"X-TPI-Service-Token": "invalid-token-123"},
        json={"system_prompt": "sys", "user_prompt": "usr"},
    )
    assert response.status_code == 401


def test_endpoint_missing_groq_key_fails_503():
    from app.core.config import get_settings

    token = get_settings().tpi_internal_service_token
    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=None)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/internal/llm/generate",
            headers={
                "X-TPI-Service-Token": token,
                "X-Consumer-Engine": "agent",
            },
            json={
                "system_prompt": "sys",
                "user_prompt": "usr",
                "consumer": "agent",
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["code"] == "PROVIDER_UNAVAILABLE"
        assert "LLM provider is not configured" in data["detail"]["message"]
    finally:
        app.dependency_overrides.clear()


def test_endpoint_successful_generation_flow():
    from app.contracts.llm import LLMGenerateResponse, LLMUsage
    from app.core.config import get_settings

    token = get_settings().tpi_internal_service_token

    class MockProvider:
        name = "groq"
        model = "llama-3.3-70b-versatile"

        async def generate(self, *, system_prompt, user_prompt, temperature, max_tokens):
            return LLMGenerateResponse(
                text="Generated answer",
                provider="groq",
                model=self.model,
                usage=LLMUsage(input_tokens=10, output_tokens=5),
            )

    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=MockProvider())

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/internal/llm/generate",
            headers={
                "X-TPI-Service-Token": token,
                "X-Consumer-Engine": "agent",
            },
            json={
                "system_prompt": "sys",
                "user_prompt": "usr",
                "temperature": 0.2,
                "max_tokens": 500,
                "consumer": "agent",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Generated answer"
        assert data["provider"] == "groq"
        assert data["model"] == "llama-3.3-70b-versatile"
        assert data["usage"]["input_tokens"] == 10
        assert data["usage"]["output_tokens"] == 5
    finally:
        app.dependency_overrides.clear()
