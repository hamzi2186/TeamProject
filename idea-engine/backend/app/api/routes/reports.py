import os
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.common import APIResponse
from app.schemas.reports import (
    DailyReportGenerateRequest,
    IdeaReportRunResponse,
)
from app.services.report_service import (
    generate_daily_report,
    get_report_detail,
    list_daily_reports,
)

router = APIRouter(prefix="/idea/reports", tags=["Reports"])


@router.post("/daily/generate", response_model=APIResponse[IdeaReportRunResponse])
async def generate_daily_report_endpoint(
    request: DailyReportGenerateRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    x_user_id: UUID | None = Header(default=None),
) -> APIResponse[IdeaReportRunResponse]:
    """
    Triggers end-of-day / daily lead intelligence report generation.
    Aggregates Calling, SMS, and Mailer interactions, resolves canonical outcomes,
    and builds the downloadable .docx report.
    """
    target_date = (
        request.report_date
        if (request and request.report_date)
        else datetime.now(timezone.utc).date()
    )

    try:
        report = await generate_daily_report(session, target_date, user_id=x_user_id)
        return APIResponse.ok(report)
    except Exception as exc:
        return APIResponse.fail(
            code="REPORT_GENERATION_FAILED",
            message=f"Failed to generate daily report: {exc}",
        )


@router.get("/daily", response_model=APIResponse[list[IdeaReportRunResponse]])
async def list_daily_reports_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[list[IdeaReportRunResponse]]:
    """
    Lists historical daily reports with high-level outcome distribution KPI counts.
    """
    offset = (page - 1) * page_size
    reports = await list_daily_reports(session, limit=page_size, offset=offset)
    return APIResponse.ok(reports)


@router.get("/{report_id}", response_model=APIResponse[IdeaReportRunResponse])
async def get_report_detail_endpoint(
    report_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[IdeaReportRunResponse]:
    """
    Retrieves full details of a specific daily report, including all individual lead items.
    """
    report = await get_report_detail(session, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return APIResponse.ok(report)


@router.get("/{report_id}/download")
async def download_report_docx_endpoint(
    report_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """
    Streams and downloads the generated .docx Lead Intelligence report file.
    """
    report = await get_report_detail(session, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    filename = report.document_filename or f"t-rex-report-{report.report_date}.docx"

    # Verify file exists on disk, else re-generate
    from app.core.config import get_settings
    from app.services.docx_generator import build_daily_docx_report

    settings = get_settings()
    file_path = os.path.join(settings.reports_storage_dir, filename)

    if not os.path.exists(file_path):
        os.makedirs(settings.reports_storage_dir, exist_ok=True)
        build_daily_docx_report(report, file_path)

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
