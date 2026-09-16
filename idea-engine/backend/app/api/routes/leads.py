from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.common import APIResponse
from app.schemas.reports import LeadJourneySummaryResponse
from app.services.report_service import get_lead_journey_summary

router = APIRouter(prefix="/idea/leads", tags=["Leads"])


@router.get("/{lead_id}/summary", response_model=APIResponse[LeadJourneySummaryResponse])
async def get_lead_summary_endpoint(
    lead_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[LeadJourneySummaryResponse]:
    """
    Returns real-time 360-degree multi-channel lead intelligence:
    - Unified chronological touchpoint timeline (calls, SMS, emails)
    - Approach order & channel summary
    - Canonical outcome evaluation with evidence
    - Recommended operational next action
    """
    summary = await get_lead_journey_summary(session, lead_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Lead not found")
    return APIResponse.ok(summary)
