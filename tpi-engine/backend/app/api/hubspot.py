from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.dependencies import require_service_token
from app.core.config import get_settings
from app.providers.hubspot.errors import (
    HubSpotConfigurationError,
    HubSpotError,
    InvalidOAuthStateError,
    OAuthDeniedError,
    TokenExchangeError,
)
from app.providers.hubspot.schemas import (
    ConnectionStatusResponse,
    ConnectRequest,
    ConnectResponse,
    ContactPageResponse,
)
from app.providers.hubspot.service import (
    HubSpotService,
    error_payload,
    get_hubspot_service,
)

internal_router = APIRouter(
    prefix="/api/v1/internal/hubspot",
    tags=["internal-hubspot"],
    dependencies=[Depends(require_service_token)],
)
def provider_error(error: HubSpotError) -> HTTPException:
    return HTTPException(status_code=error.http_status, detail=error_payload(error)["error"])


def frontend_callback_redirect(outcome: str, reason: str | None = None) -> RedirectResponse:
    frontend = urlsplit(get_settings().frontend_url)
    query = dict(parse_qsl(frontend.query, keep_blank_values=True))
    query["hubspot"] = outcome
    if reason:
        query["reason"] = reason
    destination = urlunsplit(
        (
            frontend.scheme,
            frontend.netloc,
            f"{frontend.path.rstrip('/')}/hubspot",
            urlencode(query),
            "",
        )
    )
    return RedirectResponse(destination, status_code=303)


def callback_error_reason(error: HubSpotError) -> str:
    if isinstance(error, (HubSpotConfigurationError, TokenExchangeError)):
        return "configuration"
    if isinstance(error, InvalidOAuthStateError):
        return "state"
    if isinstance(error, OAuthDeniedError):
        return "denied"
    return "authorization_failed"


@internal_router.post("/connect", response_model=ConnectResponse)
async def connect(
    payload: ConnectRequest,
    service: Annotated[HubSpotService, Depends(get_hubspot_service)],
) -> ConnectResponse:
    try:
        return await service.create_authorization_url(payload.user_id)
    except HubSpotError as exc:
        raise provider_error(exc) from exc


@internal_router.get("/status", response_model=ConnectionStatusResponse)
async def status(
    user_id: UUID,
    service: Annotated[HubSpotService, Depends(get_hubspot_service)],
) -> ConnectionStatusResponse:
    try:
        return await service.connection_status(user_id)
    except HubSpotError as exc:
        raise provider_error(exc) from exc


@internal_router.get("/contacts", response_model=ContactPageResponse)
async def contacts(
    user_id: UUID,
    service: Annotated[HubSpotService, Depends(get_hubspot_service)],
    after: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> ContactPageResponse:
    try:
        page = await service.contacts(user_id, after=after, limit=limit)
        return ContactPageResponse(contacts=page.contacts, next_after=page.next_after)
    except HubSpotError as exc:
        raise provider_error(exc) from exc


async def callback(
    state: str,
    service: Annotated[HubSpotService, Depends(get_hubspot_service)],
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    try:
        await service.complete_oauth(state=state, code=code, provider_error=error)
    except HubSpotError as exc:
        return frontend_callback_redirect("error", callback_error_reason(exc))
    return frontend_callback_redirect("connected")
