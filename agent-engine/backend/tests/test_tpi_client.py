import json

import httpx
import pytest

from app.services.tpi_client import TPIEmbeddingClient, TPIEmbeddingError


@pytest.mark.asyncio
async def test_tpi_client_sends_headers_and_payload():
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        body = json.loads(request.content)
        count = len(body.get("texts", [body.get("text")]))
        return httpx.Response(
            200,
            json={
                "embeddings": [[0.1] * 1024 for _ in range(count)],
                "provider": "agent-jina",
                "model": "jina-embeddings-v3",
                "dimension": 1024,
            },
        )

    client = TPIEmbeddingClient(
        base_url="http://fake-tpi:8001",
        service_token="test-service-token",
        default_provider="jina",
        default_model="jina-embeddings-v3",
        default_dimension=1024,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    # Test passages
    res_passages = await client.passages(["hello world", "test two"])
    assert len(res_passages.embeddings) == 2
    assert res_passages.dimension == 1024

    req1 = captured_requests[0]
    assert req1.headers["X-TPI-Service-Token"] == "test-service-token"
    assert req1.headers["X-Consumer-Engine"] == "agent"
    body1 = json.loads(req1.content)
    assert body1["consumer"] == "agent"
    assert body1["provider"] == "jina"

    # Test query
    res_query = await client.query("search query")
    assert len(res_query.embeddings) == 1
    req2 = captured_requests[1]
    assert req2.headers["X-Consumer-Engine"] == "agent"
    body2 = json.loads(req2.content)
    assert body2["consumer"] == "agent"
    assert body2["text"] == "search query"


@pytest.mark.asyncio
async def test_tpi_client_error_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503, json={"detail": {"code": "SERVICE_UNAVAILABLE", "retryable": True}}
        )

    client = TPIEmbeddingClient(
        base_url="http://fake-tpi:8001",
        service_token="test-service-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(TPIEmbeddingError) as exc_info:
        await client.passages(["fail test"])

    assert exc_info.value.retryable is True
    assert exc_info.value.code == "SERVICE_UNAVAILABLE"

