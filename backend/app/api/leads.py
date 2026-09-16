from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_lead_repository, get_scraper_client
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.schemas.leads import (
    LeadBuildKnowledgeBaseRequest,
    LeadKnowledgeBaseStatusResponse,
    LeadResponse,
    LeadSearchKnowledgeBaseRequest,
    LeadSearchKnowledgeBaseResponse,
    LeadSearchResultItem,
    LeadUpdate,
)
from app.services.leads import LeadRepository
from app.services.scraper_client import ScraperClient, ScraperClientError

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


def map_knowledge_base_status(
    website: dict, job: dict | None, lead_website_url: str | None
) -> LeadKnowledgeBaseStatusResponse:
    kb_status = (website.get("kb_status") or "").upper()
    crawl_status = (website.get("crawl_status") or "").upper()
    job_status = (job.get("status") if job else "").upper()

    if job_status == "QUEUED":
        status = "QUEUED"
    elif crawl_status == "CRAWLING" or kb_status == "CRAWLING":
        status = "CRAWLING"
    elif kb_status in {"EMBEDDING", "PROCESSING", "REFRESHING"}:
        status = "PROCESSING / EMBEDDING"
    elif kb_status == "READY":
        status = "READY"
    elif kb_status == "PARTIAL":
        status = "PARTIAL"
    elif kb_status == "FAILED" or job_status == "FAILED":
        status = "FAILED"
    elif job_status == "RUNNING":
        status = "CRAWLING"
    elif kb_status:
        status = kb_status
    else:
        status = "NOT_CREATED"

    error_message = (job.get("error_message") if job else None) or website.get("last_error")

    return LeadKnowledgeBaseStatusResponse(
        has_website=bool(website.get("original_url") or lead_website_url),
        website_url=website.get("original_url") or lead_website_url,
        website_id=website.get("id"),
        knowledge_base_id=website.get("knowledge_base_id"),
        status=status,
        page_count=website.get("page_count", 0),
        chunk_count=website.get("chunk_count", 0),
        last_indexed_at=website.get("last_crawled_at"),
        error_message=error_message,
    )


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


@router.get("/{lead_id}/knowledge-base", response_model=LeadKnowledgeBaseStatusResponse)
async def get_lead_knowledge_base(
    lead_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
    scraper: Annotated[ScraperClient, Depends(get_scraper_client)],
) -> LeadKnowledgeBaseStatusResponse:
    lead = await leads.get_for_user(user.user_id, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")

    if lead.website_id:
        try:
            status_data = await scraper.get_website_status(user.user_id, user.role, lead.website_id)
        except ScraperClientError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        if status_data:
            return map_knowledge_base_status(
                status_data["website"], status_data.get("job"), lead.website_url
            )

    if lead.website_url:
        try:
            website = await scraper.lookup_website_by_url(user.user_id, user.role, lead.website_url)
        except ScraperClientError:
            website = None
        if website:
            await leads.set_lead_website(user.user_id, lead.id, website["id"])
            try:
                status_data = await scraper.get_website_status(
                    user.user_id, user.role, website["id"]
                )
            except ScraperClientError as exc:
                raise HTTPException(exc.status_code, str(exc)) from exc
            if status_data:
                return map_knowledge_base_status(
                    status_data["website"], status_data.get("job"), lead.website_url
                )

    return LeadKnowledgeBaseStatusResponse(
        has_website=bool(lead.website_url),
        website_url=lead.website_url,
        website_id=None,
        knowledge_base_id=None,
        status="NOT_CREATED",
        page_count=0,
        chunk_count=0,
    )


@router.post("/{lead_id}/knowledge-base/build", response_model=LeadKnowledgeBaseStatusResponse)
async def build_lead_knowledge_base(
    lead_id: UUID,
    payload: LeadBuildKnowledgeBaseRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
    scraper: Annotated[ScraperClient, Depends(get_scraper_client)],
) -> LeadKnowledgeBaseStatusResponse:
    lead = await leads.get_for_user(user.user_id, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")

    target_url = (payload.website_url or lead.website_url or "").strip()
    if not target_url:
        raise HTTPException(400, "Website URL is required to build a knowledge base")

    try:
        ingest_result = await scraper.ingest_website(
            user.user_id, user.role, url=target_url, lead_ids=[lead.id]
        )
    except ScraperClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    website = ingest_result["website"]
    await leads.set_lead_website(user.user_id, lead.id, website["id"], website_url=target_url)

    try:
        status_data = await scraper.get_website_status(user.user_id, user.role, website["id"])
    except ScraperClientError:
        status_data = {"website": website, "job": None}

    return map_knowledge_base_status(
        status_data["website"] if status_data else website,
        status_data.get("job") if status_data else None,
        target_url,
    )


@router.post("/{lead_id}/knowledge-base/refresh", response_model=LeadKnowledgeBaseStatusResponse)
async def refresh_lead_knowledge_base(
    lead_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
    scraper: Annotated[ScraperClient, Depends(get_scraper_client)],
) -> LeadKnowledgeBaseStatusResponse:
    lead = await leads.get_for_user(user.user_id, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")

    if not lead.website_id:
        if lead.website_url:
            return await build_lead_knowledge_base(
                lead_id,
                LeadBuildKnowledgeBaseRequest(website_url=lead.website_url),
                user,
                leads,
                scraper,
            )
        raise HTTPException(400, "Lead has no website associated to refresh")

    try:
        refresh_result = await scraper.refresh_website(user.user_id, user.role, lead.website_id)
    except ScraperClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    website = refresh_result["website"]
    try:
        status_data = await scraper.get_website_status(user.user_id, user.role, lead.website_id)
    except ScraperClientError:
        status_data = {"website": website, "job": None}

    return map_knowledge_base_status(
        status_data["website"] if status_data else website,
        status_data.get("job") if status_data else None,
        lead.website_url,
    )


@router.post("/{lead_id}/knowledge-base/search", response_model=LeadSearchKnowledgeBaseResponse)
async def search_lead_knowledge_base(
    lead_id: UUID,
    payload: LeadSearchKnowledgeBaseRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
    scraper: Annotated[ScraperClient, Depends(get_scraper_client)],
) -> LeadSearchKnowledgeBaseResponse:
    lead = await leads.get_for_user(user.user_id, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")

    if not lead.website_id:
        raise HTTPException(400, "Knowledge base has not been created for this lead")

    try:
        status_data = await scraper.get_website_status(user.user_id, user.role, lead.website_id)
    except ScraperClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    if not status_data or not status_data.get("website", {}).get("knowledge_base_id"):
        raise HTTPException(400, "Knowledge base has not been created for this lead")

    kb_id = status_data["website"]["knowledge_base_id"]

    try:
        search_data = await scraper.search_knowledge_base(
            user.user_id, user.role, kb_id, payload.query, top_k=payload.top_k
        )
    except ScraperClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    return LeadSearchKnowledgeBaseResponse(
        knowledge_base_id=search_data["knowledge_base_id"],
        query=search_data["query"],
        results=[
            LeadSearchResultItem(
                chunk_id=item["chunk_id"],
                content=item["content"],
                source_url=item["source_url"],
                page_title=item.get("page_title"),
                similarity=item["similarity"],
            )
            for item in search_data.get("results", [])
        ],
    )
