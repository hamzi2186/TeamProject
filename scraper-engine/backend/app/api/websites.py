from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import TaskDispatcher, get_repository, get_task_dispatcher
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.repositories.scraper import ScraperRepository, WebsiteSummary
from app.schemas.scraper import (
    IngestRequest,
    IngestResponse,
    JobResponse,
    KnowledgeBaseResponse,
    NormalizeRequest,
    NormalizeResponse,
    PageResponse,
    WebsiteResponse,
)
from app.services.ssrf import UnsafeTargetError, validate_public_url
from app.services.urls import URLValidationError, normalize_website_url

router = APIRouter(prefix="/api/v1", tags=["client-knowledge"])


def website_response(summary: WebsiteSummary) -> WebsiteResponse:
    website = summary.website
    return WebsiteResponse(
        id=website.id,
        original_url=website.original_url,
        normalized_url=website.normalized_url,
        normalized_key=website.normalized_key,
        crawl_status=website.crawl_status,
        last_crawled_at=website.last_crawled_at,
        content_fingerprint=website.content_fingerprint,
        created_at=website.created_at,
        updated_at=website.updated_at,
        knowledge_base_id=summary.knowledge_base_id,
        kb_status=summary.kb_status,
        page_count=summary.page_count,
        chunk_count=summary.chunk_count,
        leads_using_kb=summary.leads_using_kb,
    )


async def validated_normalization(raw_url: str):
    try:
        normalized = normalize_website_url(raw_url)
        await validate_public_url(normalized.normalized_url)
        return normalized
    except UnsafeTargetError as exc:
        raise HTTPException(400, "Website target is not allowed") from exc
    except URLValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/websites/normalize", response_model=NormalizeResponse)
async def normalize(
    payload: NormalizeRequest,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> NormalizeResponse:
    result = await validated_normalization(payload.url)
    return NormalizeResponse(**result.__dict__)


@router.post("/websites/ingest", response_model=IngestResponse, status_code=202)
async def ingest(
    payload: IngestRequest,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
    dispatcher: Annotated[TaskDispatcher, Depends(get_task_dispatcher)],
) -> IngestResponse:
    normalized = await validated_normalization(payload.url)
    try:
        website, kb, job, reused = await repository.create_site_kb_job(
            user_id=current.user_id,
            original_url=payload.url.strip(),
            normalized_url=normalized.normalized_url,
            normalized_key=normalized.normalized_key,
            lead_ids=payload.lead_ids,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    if job is not None and not reused:
        task_id = dispatcher.dispatch(job.id)
        await repository.set_task_id(job.id, task_id)
    summary = await repository.website_summary(current.user_id, website.id)
    return IngestResponse(
        website=website_response(summary),
        knowledge_base_id=kb.id,
        job_id=job.id if job else None,
        reused=reused,
    )


@router.get("/websites", response_model=list[WebsiteResponse])
async def list_websites(
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> list[WebsiteResponse]:
    return [website_response(item) for item in await repository.list_websites(current.user_id)]


@router.get("/websites/{website_id}", response_model=WebsiteResponse)
async def get_website(
    website_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> WebsiteResponse:
    summary = await repository.website_summary(current.user_id, website_id)
    if summary is None:
        raise HTTPException(404, "Website not found")
    return website_response(summary)


@router.get("/websites/{website_id}/status")
async def website_status(
    website_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> dict:
    summary = await repository.website_summary(current.user_id, website_id)
    if summary is None:
        raise HTTPException(404, "Website not found")
    job = await repository.latest_job(current.user_id, website_id)
    return {
        "website": website_response(summary),
        "job": JobResponse.model_validate(job) if job else None,
    }


@router.get("/websites/{website_id}/pages", response_model=list[PageResponse])
async def website_pages(
    website_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> list[PageResponse]:
    if await repository.website_for_user(current.user_id, website_id) is None:
        raise HTTPException(404, "Website not found")
    return [
        PageResponse.model_validate(page)
        for page in await repository.pages_for_website(current.user_id, website_id)
    ]


@router.post("/websites/{website_id}/refresh", response_model=IngestResponse, status_code=202)
async def refresh_website(
    website_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
    dispatcher: Annotated[TaskDispatcher, Depends(get_task_dispatcher)],
) -> IngestResponse:
    website = await repository.website_for_user(current.user_id, website_id)
    if website is None:
        raise HTTPException(404, "Website not found")
    website, kb, job, reused = await repository.create_site_kb_job(
        user_id=current.user_id,
        original_url=website.original_url,
        normalized_url=website.normalized_url,
        normalized_key=website.normalized_key,
        lead_ids=[],
        force_refresh=True,
        website_id=website.id,
    )
    if job is not None and not reused:
        task_id = dispatcher.dispatch(job.id)
        await repository.set_task_id(job.id, task_id)
    summary = await repository.website_summary(current.user_id, website.id)
    return IngestResponse(
        website=website_response(summary),
        knowledge_base_id=kb.id,
        job_id=job.id if job else None,
        reused=reused,
    )


@router.get("/scrape-jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> JobResponse:
    job = await repository.job_for_user(current.user_id, job_id)
    if job is None:
        raise HTTPException(404, "Scrape job not found")
    return JobResponse.model_validate(job)


@router.get("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    knowledge_base_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> KnowledgeBaseResponse:
    kb = await repository.knowledge_base_for_user(current.user_id, knowledge_base_id)
    if kb is None:
        raise HTTPException(404, "Knowledge base not found")
    return KnowledgeBaseResponse.model_validate(kb)
