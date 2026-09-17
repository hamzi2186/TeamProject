from functools import lru_cache
from typing import Any
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.hubspot import (
    HubSpotConnectionStatus,
    HubSpotConnectResponse,
    HubSpotContactPage,
)


class TPIHubSpotError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class TPIHubSpotClient:
    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._http = http_client or httpx.AsyncClient(timeout=30)

    async def connect(self, user_id: UUID) -> HubSpotConnectResponse:
        payload = await self._request(
            "POST",
            "/api/v1/internal/hubspot/connect",
            json={"user_id": str(user_id)},
        )
        return self._validate(HubSpotConnectResponse, payload)

    async def connect_token(self, user_id: UUID, access_token: str) -> HubSpotConnectionStatus:
        payload = await self._request(
            "POST",
            "/api/v1/internal/hubspot/connect-token",
            json={"user_id": str(user_id), "access_token": access_token},
        )
        return self._validate(HubSpotConnectionStatus, payload)

    async def disconnect(self, user_id: UUID) -> HubSpotConnectionStatus:
        payload = await self._request(
            "POST",
            "/api/v1/internal/hubspot/disconnect",
            json={"user_id": str(user_id)},
        )
        return self._validate(HubSpotConnectionStatus, payload)

    async def status(self, user_id: UUID) -> HubSpotConnectionStatus:
        payload = await self._request(
            "GET", "/api/v1/internal/hubspot/status", params={"user_id": str(user_id)}
        )
        return self._validate(HubSpotConnectionStatus, payload)

    async def contacts(
        self, user_id: UUID, *, after: str | None = None, limit: int = 100
    ) -> HubSpotContactPage:
        params: dict[str, str | int] = {"user_id": str(user_id), "limit": limit}
        if after:
            params["after"] = after
        payload = await self._request(
            "GET", "/api/v1/internal/hubspot/contacts", params=params
        )
        return self._validate(HubSpotContactPage, payload)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._http.request(
                method,
                f"{self._base_url}{path}",
                headers={"X-TPI-Service-Token": self._service_token},
                **kwargs,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TPIHubSpotError("HubSpot integration is temporarily unavailable", 503) from exc
        if response.status_code >= 400:
            err_msg = "HubSpot integration request failed"
            try:
                err_data = response.json()
                if isinstance(err_data, dict):
                    err_msg = err_data.get("detail") or err_data.get("error") or err_msg
            except Exception:
                pass
            status = response.status_code if response.status_code in {400, 401, 403, 404, 409} else 503
            raise TPIHubSpotError(err_msg, status)
        try:
            payload = response.json()
        except ValueError as exc:
            raise TPIHubSpotError("HubSpot integration returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise TPIHubSpotError("HubSpot integration returned an invalid response")
        return payload

    @staticmethod
    def _validate(model, payload: dict[str, Any]):
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise TPIHubSpotError("HubSpot integration returned an invalid response") from exc


@lru_cache
def get_tpi_hubspot_client() -> TPIHubSpotClient:
    settings = get_settings()
    return TPIHubSpotClient(
        base_url=settings.tpi_api_base_url,
        service_token=settings.tpi_internal_service_token,
    )
