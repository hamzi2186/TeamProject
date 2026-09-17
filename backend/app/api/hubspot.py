from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_hubspot_import_service
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.schemas.hubspot import (
    HubSpotConnectionStatus,
    HubSpotConnectResponse,
    HubSpotContactPage,
    HubSpotImportRequest,
    HubSpotImportResponse,
)
from app.services.hubspot_import import HubSpotImportService
from app.services.tpi_hubspot import (
    TPIHubSpotClient,
    TPIHubSpotError,
    get_tpi_hubspot_client,
)

router = APIRouter(prefix="/api/v1/hubspot", tags=["hubspot"])


def normalized_error(error: TPIHubSpotError) -> HTTPException:
    return HTTPException(error.status_code, str(error))


@router.get("/connect", response_model=HubSpotConnectResponse)
async def connect(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    tpi: Annotated[TPIHubSpotClient, Depends(get_tpi_hubspot_client)],
) -> HubSpotConnectResponse:
    try:
        return await tpi.connect(user.user_id)
    except TPIHubSpotError as exc:
        raise normalized_error(exc) from exc


@router.get("/status", response_model=HubSpotConnectionStatus)
async def status(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    tpi: Annotated[TPIHubSpotClient, Depends(get_tpi_hubspot_client)],
) -> HubSpotConnectionStatus:
    try:
        return await tpi.status(user.user_id)
    except TPIHubSpotError as exc:
        raise normalized_error(exc) from exc


@router.get("/contacts", response_model=HubSpotContactPage)
async def contacts(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    tpi: Annotated[TPIHubSpotClient, Depends(get_tpi_hubspot_client)],
    after: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> HubSpotContactPage:
    try:
        return await tpi.contacts(user.user_id, after=after, limit=limit)
    except TPIHubSpotError as exc:
        raise normalized_error(exc) from exc


@router.post("/import", response_model=HubSpotImportResponse)
async def import_contacts(
    payload: HubSpotImportRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[HubSpotImportService, Depends(get_hubspot_import_service)],
) -> HubSpotImportResponse:
    try:
        result = await service.run(user.user_id, user.role, payload)
        return HubSpotImportResponse(**result.__dict__)
    except TPIHubSpotError as exc:
        raise normalized_error(exc) from exc
