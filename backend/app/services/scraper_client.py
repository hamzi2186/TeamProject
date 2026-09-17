from functools import lru_cache
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.security import create_access_token


class ScraperClientError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ScraperClient:
    def __init__(self, base_url: str, http_client: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=30, trust_env=False)

    def _auth_header(self, user_id: UUID, role: str) -> dict[str, str]:
        token, _ = create_access_token(user_id, role)
        return {"Authorization": f"Bearer {token}"}

    async def normalize_website(self, user_id: UUID, role: str, url: str) -> dict:
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/websites/normalize",
                headers=self._auth_header(user_id, role),
                json={"url": url},
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ScraperClientError("Scraper service is unreachable", status_code=503) from exc
        if response.status_code >= 400:
            error_detail = "Website URL could not be normalized"
            try:
                error_detail = response.json().get("detail", error_detail)
            except Exception:
                pass
            raise ScraperClientError(error_detail, status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ScraperClientError("Scraper service returned an invalid response") from exc
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("normalized_url"), str)
            or not isinstance(payload.get("normalized_key"), str)
        ):
            raise ScraperClientError("Scraper service returned an invalid response")
        return payload

    async def get_website_status(self, user_id: UUID, role: str, website_id: UUID) -> dict | None:
        try:
            response = await self._client.get(
                f"{self._base_url}/api/v1/websites/{website_id}/status",
                headers=self._auth_header(user_id, role),
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ScraperClientError("Scraper service is unreachable", status_code=503) from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise ScraperClientError(
                f"Scraper service returned error: {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def lookup_website_by_url(self, user_id: UUID, role: str, url: str) -> dict | None:
        try:
            response = await self._client.get(
                f"{self._base_url}/api/v1/websites",
                params={"url": url},
                headers=self._auth_header(user_id, role),
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ScraperClientError("Scraper service is unreachable", status_code=503) from exc
        if response.status_code >= 400:
            raise ScraperClientError(
                f"Scraper service returned error: {response.text}",
                status_code=response.status_code,
            )
        data = response.json()
        return data[0] if data else None

    async def ingest_website(
        self, user_id: UUID, role: str, url: str, lead_ids: list[UUID]
    ) -> dict:
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/websites/ingest",
                headers=self._auth_header(user_id, role),
                json={"url": url, "lead_ids": [str(lid) for lid in lead_ids]},
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ScraperClientError("Scraper service is unreachable", status_code=503) from exc
        if response.status_code >= 400:
            error_detail = "Could not start website ingestion"
            try:
                error_detail = response.json().get("detail", error_detail)
            except Exception:
                pass
            raise ScraperClientError(error_detail, status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ScraperClientError("Scraper service returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise ScraperClientError("Scraper service returned an invalid response")
        return payload

    async def refresh_website(self, user_id: UUID, role: str, website_id: UUID) -> dict:
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/websites/{website_id}/refresh",
                headers=self._auth_header(user_id, role),
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ScraperClientError("Scraper service is unreachable", status_code=503) from exc
        if response.status_code >= 400:
            error_detail = "Could not refresh website ingestion"
            try:
                error_detail = response.json().get("detail", error_detail)
            except Exception:
                pass
            raise ScraperClientError(error_detail, status_code=response.status_code)
        return response.json()

    async def search_knowledge_base(
        self, user_id: UUID, role: str, kb_id: UUID, query: str, top_k: int = 6
    ) -> dict:
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/knowledge-bases/{kb_id}/search",
                headers=self._auth_header(user_id, role),
                json={"query": query, "top_k": top_k},
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ScraperClientError("Scraper service is unreachable", status_code=503) from exc
        if response.status_code >= 400:
            error_detail = "Knowledge base search failed"
            try:
                error_detail = response.json().get("detail", error_detail)
            except Exception:
                pass
            raise ScraperClientError(error_detail, status_code=response.status_code)
        return response.json()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


@lru_cache
def get_scraper_client() -> ScraperClient:
    settings = get_settings()
    return ScraperClient(base_url=settings.scraper_api_base_url)

