import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.embeddings.errors import (
    EmbeddingDimensionError,
    EmbeddingRateLimitError,
    MalformedEmbeddingResponseError,
)
from app.providers.embeddings.jina import JINA_EMBEDDINGS_URL, JinaEmbeddingProvider
from app.providers.embeddings.local import LocalHashEmbeddingProvider
from app.providers.embeddings.service import EmbeddingService, get_embedding_service


def jina_provider(handler, *, dimension: int = 3) -> JinaEmbeddingProvider:
    return JinaEmbeddingProvider(
        api_key="test-only-key",
        model="jina-embeddings-v3",
        dimension=dimension,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("task", ["retrieval.passage", "retrieval.query"])
async def test_jina_tasks_batching_and_normalized_response(task):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == JINA_EMBEDDINGS_URL
        assert request.headers["authorization"] == "Bearer test-only-key"
        body = json.loads(request.content)
        assert body["task"] == task
        assert body["model"] == "jina-embeddings-v3"
        assert body["dimensions"] == 3
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [float(index), 0.5, -0.5]}
                    for index, _ in enumerate(body["input"])
                ]
            },
        )

    provider = jina_provider(handler)
    if task == "retrieval.passage":
        from app.contracts.embeddings import EmbeddingTask

        result = await provider.embed(["one", "two"], task=EmbeddingTask.PASSAGE)
        assert len(result.embeddings) == 2
    else:
        from app.contracts.embeddings import EmbeddingTask

        result = await provider.embed(["question"], task=EmbeddingTask.QUERY)
        assert len(result.embeddings) == 1
    assert (result.provider, result.model, result.dimension) == (
        "jina",
        "jina-embeddings-v3",
        3,
    )


@pytest.mark.asyncio
async def test_jina_rate_limit_and_malformed_response_are_normalized():
    from app.contracts.embeddings import EmbeddingTask

    with pytest.raises(EmbeddingRateLimitError):
        await jina_provider(lambda _: httpx.Response(429, json={"secret": "hidden"})).embed(
            ["text"], task=EmbeddingTask.PASSAGE
        )
    with pytest.raises(MalformedEmbeddingResponseError):
        await jina_provider(lambda _: httpx.Response(200, json={"unexpected": True})).embed(
            ["text"], task=EmbeddingTask.PASSAGE
        )


@pytest.mark.asyncio
async def test_jina_dimension_mismatch_is_rejected():
    from app.contracts.embeddings import EmbeddingTask

    provider = jina_provider(
        lambda _: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})
    )
    with pytest.raises(EmbeddingDimensionError):
        await provider.embed(["text"], task=EmbeddingTask.PASSAGE)


@pytest.mark.asyncio
async def test_local_fallback_uses_distinct_stable_space():
    local = LocalHashEmbeddingProvider(model="trex-local-hash-v1", dimension=8)
    service = EmbeddingService({"local": local}, primary="missing", fallback="local")
    fallback = await service.passages(["stable text"])
    assert fallback.provider == "local"
    first = await local.embed(
        ["stable text"],
        task=__import__(
            "app.contracts.embeddings", fromlist=["EmbeddingTask"]
        ).EmbeddingTask.PASSAGE,
    )
    second = await local.embed(
        ["stable text"],
        task=__import__(
            "app.contracts.embeddings", fromlist=["EmbeddingTask"]
        ).EmbeddingTask.PASSAGE,
    )
    assert first.embeddings == second.embeddings
    assert first.provider == "local"


class FakeEmbeddingService:
    async def passages(self, texts, **_kwargs):
        from app.contracts.embeddings import EmbeddingResponse

        return EmbeddingResponse(
            embeddings=[[0.0, 1.0] for _ in texts],
            provider="jina",
            model="jina-embeddings-v3",
            dimension=2,
        )

    async def query(self, text, **_kwargs):
        return await self.passages([text])


def test_embeddings_api_requires_internal_auth_and_exposes_no_secret(monkeypatch):
    import app.api.dependencies as dependencies

    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(tpi_internal_service_token="internal-test-token"),
    )
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)
    assert (
        client.post("/api/v1/internal/embeddings/query", json={"text": "question"}).status_code
        == 422
    )
    response = client.post(
        "/api/v1/internal/embeddings/passages",
        json={"texts": ["one", "two"]},
        headers={"X-TPI-Service-Token": "internal-test-token"},
    )
    assert response.status_code == 200
    assert len(response.json()["embeddings"]) == 2
    serialized = json.dumps(response.json()).casefold()
    assert "test-only-key" not in serialized
    assert "authorization" not in serialized
    app.dependency_overrides.clear()
