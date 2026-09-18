import json

import httpx
import pytest

from app.services import tpi_client
from app.services.tpi_client import TPIServiceError


class FakeAsyncClient:
    def __init__(self, response: httpx.Response, **_: object) -> None:
        self.response = response
        self.request: tuple[str, dict] | None = None

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, path: str, **kwargs: object) -> httpx.Response:
        self.request = (path, kwargs)
        return self.response


@pytest.mark.asyncio
async def test_generate_llm_text_uses_tpi_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(
        200,
        content=json.dumps(
            {
                "text": (
                    '{"message":"Hello","outcome":null,'
                    '"should_stop":false,"reason":"Continue"}'
                ),
                "provider": "groq",
                "model": "test",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        ).encode(),
    )
    fake = FakeAsyncClient(response)
    monkeypatch.setattr(tpi_client.httpx, "AsyncClient", lambda **kwargs: fake)

    text = await tpi_client.generate_llm_text(
        system_prompt="Return JSON",
        user_prompt="Write an SMS",
        temperature=0.25,
        max_tokens=128,
    )

    assert text.startswith("{")
    assert fake.request is not None
    path, kwargs = fake.request
    assert path == "/api/v1/internal/llm/generate"
    assert kwargs["headers"]["X-Consumer-Engine"] == "sms"
    assert kwargs["json"]["consumer"] == "sms"


@pytest.mark.asyncio
async def test_generate_llm_text_rejects_tpi_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAsyncClient(httpx.Response(503, content=b'{}'))
    monkeypatch.setattr(tpi_client.httpx, "AsyncClient", lambda **kwargs: fake)

    with pytest.raises(TPIServiceError):
        await tpi_client.generate_llm_text(
            system_prompt="Return JSON",
            user_prompt="Write an SMS",
            temperature=0.25,
            max_tokens=128,
        )
