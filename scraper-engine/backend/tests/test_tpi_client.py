import httpx
import pytest

from app.services.tpi_embeddings import TPIEmbeddingClient, TPIEmbeddingError


@pytest.mark.asyncio
async def test_passage_and_query_contracts_and_dimension_validation():
    tasks = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)
        tasks.append((request.url.path, body))
        count = len(body.get("texts", [body.get("text")]))
        return httpx.Response(
            200,
            json={
                "embeddings": [[0.0, 1.0] for _ in range(count)],
                "provider": "jina",
                "model": "jina-embeddings-v3",
                "dimension": 2,
            },
        )

    client = TPIEmbeddingClient(
        base_url="http://tpi.test",
        service_token="internal",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    passages = await client.passages(["one", "two"])
    query = await client.query("question", provider="jina", model="jina-embeddings-v3", dimension=2)
    assert len(passages.embeddings) == 2
    assert len(query.embeddings) == 1
    assert tasks[0][0].endswith("/passages")
    assert tasks[1][0].endswith("/query")
    assert tasks[1][1]["provider"] == "jina"


@pytest.mark.asyncio
async def test_malformed_and_provider_errors_hide_raw_payload():
    malformed = TPIEmbeddingClient(
        base_url="http://tpi.test",
        service_token="internal",
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"secret": "x"}))
        ),
    )
    with pytest.raises(TPIEmbeddingError) as captured:
        await malformed.passages(["one"])
    assert "secret" not in str(captured.value)

    limited = TPIEmbeddingClient(
        base_url="http://tpi.test",
        service_token="internal",
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    429,
                    json={
                        "detail": {
                            "code": "PROVIDER_RATE_LIMIT",
                            "retryable": True,
                            "provider_key": "hidden",
                        }
                    },
                )
            )
        ),
    )
    with pytest.raises(TPIEmbeddingError) as captured:
        await limited.passages(["one"])
    assert captured.value.retryable is True
    assert "hidden" not in str(captured.value)
