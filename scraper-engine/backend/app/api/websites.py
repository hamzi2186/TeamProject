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
    ProcessingStatusResponse,
    WebsiteResponse,
    WebsiteStatusResponse,
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


def processing_status(summary: WebsiteSummary, job) -> ProcessingStatusResponse:
    kb_status = (summary.kb_status or "NOT_CREATED").upper()
    job_status = (job.status if job else "").upper()
    if job_status == "FAILED":
        stage = "FAILED"
    elif job_status == "QUEUED":
        stage = "QUEUED"
    elif job_status == "PARTIAL" or kb_status == "PARTIAL":
        stage = "PARTIAL"
    elif job_status == "COMPLETED" or kb_status == "READY":
        stage = "READY"
    elif job_status == "RUNNING":
        if kb_status == "EMBEDDING":
            stage = "EMBEDDING"
        elif kb_status == "PROCESSING":
            stage = "EXTRACTING"
        else:
            stage = "CRAWLING"
    elif kb_status == "FAILED":
        stage = "FAILED"
    elif kb_status == "EMBEDDING":
        stage = "EMBEDDING"
    elif kb_status == "PROCESSING":
        stage = "EXTRACTING"
    elif kb_status in {"CRAWLING", "REFRESHING"}:
        stage = "CRAWLING"
    else:
        stage = "NOT_STARTED"

    error = None
    if stage == "FAILED":
        error = _safe_processing_error(job.error_code if job else None)
    elif stage == "PARTIAL" and job and job.partial_reason:
        error = "The website was partially processed; some pages could not be included."

    terminal_success = stage in {"READY", "PARTIAL"}
    return ProcessingStatusResponse(
        knowledge_base_status=kb_status,
        processing_stage=stage,
        pages_discovered=job.pages_discovered if job else 0,
        pages_processed=job.pages_crawled if job else summary.page_count,
        pages_succeeded=job.pages_indexed if job else summary.page_count,
        pages_failed=None,
        chunks_created=job.chunks_generated if job else summary.chunk_count,
        embeddings_created=(job.chunks_generated if job and terminal_success else None),
        started_at=job.started_at if job else None,
        updated_at=job.updated_at if job else summary.website.updated_at,
        completed_at=job.completed_at if job else None,
        error=error,
    )


def _safe_processing_error(error_code: str | None) -> str:
    code = (error_code or "").upper()
    if code == "TASK_DISPATCH_FAILED":
        return "Website ingestion could not be queued. Please try again."
    if "EMBEDDING" in code or "TPI" in code:
        return "Website embeddings could not be generated. Please try again."
    if "URL" in code:
        return "The website URL could not be processed."
    if "CRAWL" in code or "HTTP" in code:
        return "Website content could not be processed. Please try again."
    return "Website knowledge processing failed. Please try again."


async def validated_normalization(raw_url: str):
    try:
        normalized = normalize_website_url(raw_url)
        await validate_public_url(normalized.normalized_url)
        return normalized
    except UnsafeTargetError as exc:
        raise HTTPException(400, "Website target is not allowed") from exc
    except URLValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


async def dispatch_job(
    *,
    repository: ScraperRepository,
    dispatcher: TaskDispatcher,
    user_id: UUID,
    job_id: UUID,
) -> None:
    try:
        task_id = dispatcher.dispatch(job_id)
    except Exception as exc:
        await repository.mark_dispatch_failed(user_id, job_id)
        raise HTTPException(503, "Website ingestion could not be queued") from exc
    await repository.set_task_id(job_id, task_id)


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
        await dispatch_job(
            repository=repository,
            dispatcher=dispatcher,
            user_id=current.user_id,
            job_id=job.id,
        )
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
    url: str | None = None,
) -> list[WebsiteResponse]:
    normalized_key: str | None = None
    if url:
        try:
            normalized = normalize_website_url(url)
            normalized_key = normalized.normalized_key
        except Exception:
            return []
    return [
        website_response(item)
        for item in await repository.list_websites(current.user_id, normalized_key=normalized_key)
    ]


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


@router.get("/websites/{website_id}/status", response_model=WebsiteStatusResponse)
async def website_status(
    website_id: UUID,
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ScraperRepository, Depends(get_repository)],
) -> WebsiteStatusResponse:
    summary = await repository.website_summary(current.user_id, website_id)
    if summary is None:
        raise HTTPException(404, "Website not found")
    job = await repository.latest_job(current.user_id, website_id)
    processing = processing_status(summary, job)
    job_response = JobResponse.model_validate(job) if job else None
    if job_response and job_response.status == "FAILED":
        job_response.error_message = processing.error
    return WebsiteStatusResponse(
        website=website_response(summary),
        job=job_response,
        processing=processing,
    )


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
        await dispatch_job(
            repository=repository,
            dispatcher=dispatcher,
            user_id=current.user_id,
            job_id=job.id,
        )
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
