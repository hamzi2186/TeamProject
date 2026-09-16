from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_lead_repository
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.schemas.leads import LeadResponse, LeadUpdate
from app.services.leads import LeadRepository

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
) -> list[LeadResponse]:
    return await leads.list_for_user(user.user_id)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
) -> LeadResponse:
    lead = await leads.get_for_user(user.user_id, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
) -> LeadResponse:
    lead = await leads.update_for_user(user.user_id, lead_id, payload)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    return lead
