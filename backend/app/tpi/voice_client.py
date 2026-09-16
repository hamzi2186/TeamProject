from typing import Any
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.security import AuthenticatedUser


class TPIVoiceError(RuntimeError):
    """Raised when the TPI voice contract cannot be reached successfully."""


class TPIVoiceClient:
    """Calling Engine client; provider HTTP remains inside the TPI service."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        settings = get_settings()
        headers = dict(kwargs.pop("headers", {}))
        if settings.tpi_internal_service_token:
            headers["X-TPI-Service-Token"] = settings.tpi_internal_service_token
        url = f"{settings.tpi_api_base_url.rstrip('/')}{path}"
        try:
            if self.client is None:
                response = httpx.request(method, url, headers=headers, timeout=settings.tpi_request_timeout_seconds, **kwargs)
            else:
                response = self.client.request(method, url, headers=headers, timeout=settings.tpi_request_timeout_seconds, **kwargs)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                err_data = exc.response.json()
                detail = err_data.get("detail") or err_data.get("message") or str(err_data)
            except Exception:
                detail = exc.response.text or str(exc)
            raise TPIVoiceError(detail) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TPIVoiceError("TPI voice service request failed") from exc
        return body.get("data", body) if isinstance(body, dict) else {"data": body}

    def start_call(self, *, user: AuthenticatedUser, lead_id: str, phone_number: str, purpose: str, campaign_id: UUID | str | None, prompt: str | None = None, lead_variables: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", "/api/v1/internal/calling/start", json={
            "user_id": str(user.user_id), "lead_id": lead_id, "phone_number": phone_number,
            "purpose": purpose, "campaign_id": str(campaign_id) if campaign_id else None,
            "prompt": prompt, "lead_variables": lead_variables or {},
        })

    def get_call(self, provider_call_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/internal/calling/{provider_call_id}")

    def cancel_call(self, provider_call_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/internal/calling/{provider_call_id}")