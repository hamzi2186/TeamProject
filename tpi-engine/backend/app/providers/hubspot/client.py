from typing import Any

import httpx
from pydantic import ValidationError

from app.providers.hubspot.errors import (
    MalformedProviderResponseError,
    ProviderAuthError,
    ProviderPermanentError,
    ProviderRateLimitError,
    ProviderTemporaryError,
    ProviderValidationError,
    TokenExchangeError,
    TokenRefreshError,
)
from app.providers.hubspot.schemas import ContactPage, HubSpotTokenSet, NormalizedContact

TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
ACCOUNT_DETAILS_URL = "https://api.hubapi.com/account-info/v3/details"
CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts"
CONTACT_PROPERTIES = ("firstname", "lastname", "phone", "email", "website")


class HubSpotClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http_client or httpx.AsyncClient(timeout=20)

    async def exchange_code(self, code: str) -> HubSpotTokenSet:
        response = await self._request(
            "POST",
            TOKEN_URL,
            operation="exchange",
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "code": code,
            },
        )
        return self._parse_token(response, require_refresh=True)

    async def refresh(self, refresh_token: str) -> HubSpotTokenSet:
        response = await self._request(
            "POST",
            TOKEN_URL,
            operation="refresh",
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
            },
        )
        return self._parse_token(response, require_refresh=False)

    async def get_portal_id(self, access_token: str) -> str:
        payload = await self._request(
            "GET", ACCOUNT_DETAILS_URL, access_token=access_token, operation="account"
        )
        portal_id = payload.get("portalId")
        if portal_id is None:
            raise MalformedProviderResponseError("HubSpot account response omitted portal ID")
        return str(portal_id)

    async def get_contacts(
        self, access_token: str, *, after: str | None = None, limit: int = 100
    ) -> ContactPage:
        params: dict[str, str | int] = {
            "properties": ",".join(CONTACT_PROPERTIES),
            "limit": min(max(limit, 1), 100),
        }
        if after:
            params["after"] = after
        payload = await self._request(
            "GET",
            CONTACTS_URL,
            access_token=access_token,
            operation="contacts",
            params=params,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise MalformedProviderResponseError("HubSpot contacts response is malformed")
        contacts: list[NormalizedContact] = []
        try:
            for item in results:
                properties = item.get("properties") or {}
                contacts.append(
                    NormalizedContact(
                        provider_contact_id=str(item["id"]),
                        firstname=properties.get("firstname"),
                        lastname=properties.get("lastname"),
                        phone=properties.get("phone"),
                        email=properties.get("email"),
                        website=properties.get("website"),
                    )
                )
        except (KeyError, TypeError, ValidationError) as exc:
            raise MalformedProviderResponseError("HubSpot contact item is malformed") from exc
        next_after = (
            payload.get("paging", {}).get("next", {}).get("after")
            if isinstance(payload.get("paging", {}), dict)
            else None
        )
        return ContactPage(contacts=contacts, next_after=str(next_after) if next_after else None)

    def _parse_token(self, payload: dict[str, Any], *, require_refresh: bool) -> HubSpotTokenSet:
        try:
            token = HubSpotTokenSet.model_validate(payload)
        except ValidationError as exc:
            raise MalformedProviderResponseError("HubSpot token response is malformed") from exc
        if require_refresh and not token.refresh_token:
            raise MalformedProviderResponseError("HubSpot token response omitted refresh token")
        return token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        operation: str,
        access_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            response = await self._http.request(method, url, headers=headers, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderTemporaryError("HubSpot is temporarily unavailable") from exc
        if response.status_code == 429:
            raise ProviderRateLimitError("HubSpot rate limit reached")
        if response.status_code in {401, 403}:
            raise ProviderAuthError("HubSpot rejected the connection credentials")
        if response.status_code >= 500:
            raise ProviderTemporaryError("HubSpot service failed temporarily")
        if response.status_code >= 400:
            if operation == "exchange":
                raise TokenExchangeError(
                    "HubSpot authorization code exchange failed. Verify that "
                    "HUBSPOT_REDIRECT_URI exactly matches the redirect URI registered in HubSpot "
                    "and that its callback host is browser-reachable."
                )
            if operation == "refresh":
                raise TokenRefreshError("HubSpot token refresh failed")
            if response.status_code == 400:
                raise ProviderValidationError("HubSpot rejected the request")
            raise ProviderPermanentError("HubSpot request failed")
        try:
            payload = response.json()
        except ValueError as exc:
            raise MalformedProviderResponseError("HubSpot returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise MalformedProviderResponseError("HubSpot returned an unexpected response")
        return payload
