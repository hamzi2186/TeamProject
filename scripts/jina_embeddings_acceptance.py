import asyncio
import os
from pathlib import Path

import httpx
from dotenv import dotenv_values


async def main() -> None:
    values = dotenv_values(Path("tpi-engine/backend/.env"))
    token = values.get("TPI_INTERNAL_SERVICE_TOKEN") or os.getenv(
        "TPI_INTERNAL_SERVICE_TOKEN"
    )
    if not token:
        raise SystemExit("TPI internal service token is not configured")
    headers = {"X-TPI-Service-Token": token}
    async with httpx.AsyncClient(
        base_url="http://localhost:8001", timeout=60, trust_env=False
    ) as client:
        passage = await client.post(
            "/api/v1/internal/embeddings/passages",
            headers=headers,
            json={
                "texts": ["Owen Clinic provides patient-focused healthcare services."]
            },
        )
        passage.raise_for_status()
        passage_data = passage.json()
        query = await client.post(
            "/api/v1/internal/embeddings/query",
            headers=headers,
            json={
                "text": "What services are available?",
                "provider": passage_data["provider"],
                "model": passage_data["model"],
                "dimension": passage_data["dimension"],
            },
        )
        query.raise_for_status()
        query_data = query.json()
    passage_dimension = len(passage_data["embeddings"][0])
    query_dimension = len(query_data["embeddings"][0])
    assert passage_data["provider"] == "jina"
    assert passage_data["model"] == "jina-embeddings-v3"
    assert passage_dimension == passage_data["dimension"] == 1024
    assert query_dimension == query_data["dimension"] == 1024
    print(
        {
            "live_provider": True,
            "provider": passage_data["provider"],
            "model": passage_data["model"],
            "passage_vectors": len(passage_data["embeddings"]),
            "query_vectors": len(query_data["embeddings"]),
            "passage_dimension": passage_dimension,
            "query_dimension": query_dimension,
            "credentials_exposed": False,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
