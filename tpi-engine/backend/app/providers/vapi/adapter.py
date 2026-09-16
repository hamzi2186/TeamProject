from typing import Any

import httpx

from app.core.config import get_settings


class VapiProviderError(RuntimeError):
    pass


class VapiAdapter:
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        settings = get_settings()
        if not settings.vapi_api_key:
            raise VapiProviderError("Vapi API key is not configured")
        try:
            response = httpx.request(
                method,
                f"https://api.vapi.ai{path}",
                headers={"Authorization": f"Bearer {settings.vapi_api_key}"},
                timeout=20,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                err_data = exc.response.json()
                detail = err_data.get("message") or str(err_data)
            except Exception:
                detail = exc.response.text or str(exc)
            raise VapiProviderError(f"Vapi request failed: {detail}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise VapiProviderError("Vapi request failed") from exc

    def start_call(self, *, phone_number: str, user_id: str, lead_id: str, purpose: str, campaign_id: str | None, prompt: str | None, lead_variables: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.vapi_assistant_id or not settings.vapi_phone_number_id:
            raise VapiProviderError("Vapi assistant and phone number are not configured")
        return self._request("POST", "/call", json={
            "assistantId": settings.vapi_assistant_id,
            "phoneNumberId": settings.vapi_phone_number_id,
            "customer": {"number": phone_number},
            "assistantOverrides": {"variableValues": {"user_id": user_id, "lead_id": lead_id, "purpose": purpose, "campaign_id": campaign_id or "", "prompt": prompt or "", **lead_variables}},
            "metadata": {"user_id": user_id, "lead_id": lead_id, "campaign_id": campaign_id},
            "serverUrl": settings.calling_internal_webhook_url,
        })

    def get_call(self, provider_call_id: str) -> dict[str, Any]:
        return self._request("GET", f"/call/{provider_call_id}")

    def cancel_call(self, provider_call_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/call/{provider_call_id}")
