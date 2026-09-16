import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import logger
from app.models.idea_reports import IdeaLeadReportItem, IdeaReportRun
from app.models.shared_reads import LeadRead
from app.schemas.enums import Channel, LeadOutcome, ReportStatus
from app.schemas.reports import (
    IdeaReportRunResponse,
    IdeaReportSummaryCounts,
    LeadJourneySummaryResponse,
    LeadReportItemResponse,
)
from app.services.aggregator import fetch_lead_events, get_active_leads_for_date
from app.services.docx_generator import build_daily_docx_report
from app.services.outcome_evaluator import evaluate_lead_outcome
from app.services.summarizer import (
    synthesize_approach_summary,
    synthesize_conversation_summary,
)


async def generate_daily_report(
    session: AsyncSession,
    target_date: date,
    user_id: UUID | None = None,
) -> IdeaReportRunResponse:
    """
    Executes the full Idea Engine pipeline:
    1. Finds active leads for the target date.
    2. Aggregates multi-channel events for each lead.
    3. Evaluates canonical outcomes and extracts evidence.
    4. Synthesizes approach timelines and conversation narratives.
    5. Persists report run and items into database.
    6. Renders and stores the final .docx report.
    """
    settings = get_settings()

    # Check for existing run for target_date
    stmt = (
        select(IdeaReportRun)
        .where(IdeaReportRun.report_date == target_date)
        .options(selectinload(IdeaReportRun.items))
    )
    existing_run = (await session.execute(stmt)).scalar_one_or_none()

    if existing_run:
        report_run = existing_run
        report_run.status = ReportStatus.PROCESSING.value
        # Clear previous items for clean idempotent re-generation
        await session.execute(
            delete(IdeaLeadReportItem).where(IdeaLeadReportItem.report_run_id == report_run.id)
        )
    else:
        report_run = IdeaReportRun(
            id=uuid.uuid4(),
            report_date=target_date,
            status=ReportStatus.PROCESSING.value,
            total_leads=0,
        )
        session.add(report_run)

    await session.commit()
    await session.refresh(report_run)

    try:
        # Fetch active leads for this date
        leads = await get_active_leads_for_date(session, target_date, user_id=user_id)
        lead_items_response: list[LeadReportItemResponse] = []
        counts = IdeaReportSummaryCounts()

        for lead in leads:
            events = await fetch_lead_events(session, lead.id)

            # Evaluate outcome
            final_outcome, outcome_reason, next_action = evaluate_lead_outcome(
                events=events,
                persisted_outcome=lead.current_status,
                current_status=lead.current_status,
            )

            # Synthesize narratives
            approach_summary = synthesize_approach_summary(events)
            lead_display = lead.display_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unnamed Lead"
            conversation_summary = await synthesize_conversation_summary(events, lead_display)

            first_act = events[0].timestamp if events else None
            last_act = events[-1].timestamp if events else None
            channels_used = sorted(list({e.channel for e in events}), key=lambda c: c.value)

            # Tally counts
            _increment_counts(counts, final_outcome)

            # Persist item
            item_record = IdeaLeadReportItem(
                id=uuid.uuid4(),
                report_run_id=report_run.id,
                user_id=lead.user_id,
                lead_id=lead.id,
                final_outcome=final_outcome.value,
                approach_summary=approach_summary,
                conversation_summary=conversation_summary,
                outcome_reason=outcome_reason,
                recommended_next_action=next_action,
                first_activity_at=first_act,
                last_activity_at=last_act,
                source_event_count=len(events),
            )
            session.add(item_record)

            lead_items_response.append(
                LeadReportItemResponse(
                    id=item_record.id,
                    lead_id=lead.id,
                    lead_name=lead_display,
                    company_website=lead.website_url,
                    phone=lead.phone,
                    email=lead.email,
                    final_outcome=final_outcome,
                    approach_summary=approach_summary,
                    conversation_summary=conversation_summary,
                    outcome_reason=outcome_reason,
                    recommended_next_action=next_action,
                    first_activity_at=first_act,
                    last_activity_at=last_act,
                    source_event_count=len(events),
                    channels_used=channels_used,
                    timeline=events,
                )
            )

        # Update report run record
        now = datetime.now(timezone.utc)
        report_run.status = ReportStatus.COMPLETED.value
        report_run.total_leads = len(leads)
        report_run.generated_at = now
        report_run.error = None

        filename = f"t-rex-daily-report-{target_date.strftime('%Y-%m-%d')}.docx"
        doc_dir = Path(settings.reports_storage_dir)
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / filename

        report_run.document_filename = filename
        report_run.document_path = str(file_path)

        counts.total_leads = len(leads)

        # Create the response DTO to feed the docx generator
        response_dto = IdeaReportRunResponse(
            id=report_run.id,
            report_date=report_run.report_date,
            status=ReportStatus.COMPLETED,
            total_leads=len(leads),
            summary_counts=counts,
            generated_at=now,
            document_filename=filename,
            download_url=f"/idea/reports/{report_run.id}/download",
            error=None,
            created_at=report_run.created_at,
            updated_at=now,
            items=lead_items_response,
        )

        # Build DOCX file
        build_daily_docx_report(response_dto, file_path)

        await session.commit()
        return response_dto

    except Exception as exc:
        logger.exception(f"Failed to generate daily report for {target_date}: {exc}")
        report_run.status = ReportStatus.FAILED.value
        report_run.error = str(exc)
        await session.commit()
        raise


async def list_daily_reports(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[IdeaReportRunResponse]:
    """
    Returns list of historical report runs with aggregated KPI counts.
    """
    stmt = (
        select(IdeaReportRun)
        .options(selectinload(IdeaReportRun.items))
        .order_by(desc(IdeaReportRun.report_date))
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(stmt)
    runs = res.scalars().all()

    results: list[IdeaReportRunResponse] = []
    for r in runs:
        counts = IdeaReportSummaryCounts()
        for item in r.items:
            if item.final_outcome in LeadOutcome.__members__:
                _increment_counts(counts, LeadOutcome(item.final_outcome))
        counts.total_leads = r.total_leads

        results.append(
            IdeaReportRunResponse(
                id=r.id,
                report_date=r.report_date,
                status=ReportStatus(r.status),
                total_leads=r.total_leads,
                summary_counts=counts,
                generated_at=r.generated_at,
                document_filename=r.document_filename,
                download_url=f"/idea/reports/{r.id}/download" if r.document_path else None,
                error=r.error,
                created_at=r.created_at,
                updated_at=r.updated_at,
                items=[],  # Summary overview does not need heavy item payloads
            )
        )
    return results


async def get_report_detail(
    session: AsyncSession,
    report_id: UUID,
) -> IdeaReportRunResponse | None:
    """
    Retrieves full report run details along with all per-lead items.
    """
    stmt = (
        select(IdeaReportRun)
        .where(IdeaReportRun.id == report_id)
        .options(selectinload(IdeaReportRun.items))
    )
    res = await session.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        return None

    # Load lead details for items
    lead_ids = [item.lead_id for item in run.items]
    lead_map: dict[UUID, LeadRead] = {}
    if lead_ids:
        lead_stmt = select(LeadRead).where(LeadRead.id.in_(lead_ids))
        leads_res = await session.execute(lead_stmt)
        for lead in leads_res.scalars().all():
            lead_map[lead.id] = lead

    items_dto: list[LeadReportItemResponse] = []
    counts = IdeaReportSummaryCounts()

    for item in run.items:
        outcome_enum = (
            LeadOutcome(item.final_outcome)
            if item.final_outcome in LeadOutcome.__members__
            else LeadOutcome.NEW
        )
        _increment_counts(counts, outcome_enum)

        lead_record = lead_map.get(item.lead_id)
        name = (
            lead_record.display_name
            or f"{lead_record.first_name or ''} {lead_record.last_name or ''}".strip()
            if lead_record
            else "Unnamed Lead"
        )
        website = lead_record.website_url if lead_record else None
        phone = lead_record.phone if lead_record else None
        email = lead_record.email if lead_record else None

        # Fetch timeline for the item
        timeline = await fetch_lead_events(session, item.lead_id)
        channels = sorted(list({e.channel for e in timeline}), key=lambda c: c.value)

        items_dto.append(
            LeadReportItemResponse(
                id=item.id,
                lead_id=item.lead_id,
                lead_name=name,
                company_website=website,
                phone=phone,
                email=email,
                final_outcome=outcome_enum,
                approach_summary=item.approach_summary,
                conversation_summary=item.conversation_summary,
                outcome_reason=item.outcome_reason,
                recommended_next_action=item.recommended_next_action,
                first_activity_at=item.first_activity_at,
                last_activity_at=item.last_activity_at,
                source_event_count=item.source_event_count,
                channels_used=channels,
                timeline=timeline,
            )
        )

    counts.total_leads = run.total_leads

    return IdeaReportRunResponse(
        id=run.id,
        report_date=run.report_date,
        status=ReportStatus(run.status),
        total_leads=run.total_leads,
        summary_counts=counts,
        generated_at=run.generated_at,
        document_filename=run.document_filename,
        download_url=f"/idea/reports/{run.id}/download" if run.document_path else None,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
        items=items_dto,
    )


async def get_lead_journey_summary(
    session: AsyncSession,
    lead_id: UUID,
) -> LeadJourneySummaryResponse | None:
    """
    Provides real-time multi-channel lead intelligence for a single lead.
    """
    lead = (await session.execute(select(LeadRead).where(LeadRead.id == lead_id))).scalar_one_or_none()
    if not lead:
        return None

    events = await fetch_lead_events(session, lead_id)
    final_outcome, outcome_reason, next_action = evaluate_lead_outcome(
        events=events,
        persisted_outcome=lead.current_status,
        current_status=lead.current_status,
    )

    approach = synthesize_approach_summary(events)
    lead_name = lead.display_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unnamed Lead"
    conv_summary = await synthesize_conversation_summary(events, lead_name)
    channels = sorted(list({e.channel for e in events}), key=lambda c: c.value)

    return LeadJourneySummaryResponse(
        lead_id=lead.id,
        lead_name=lead_name,
        phone=lead.phone,
        email=lead.email,
        website_url=lead.website_url,
        current_status=lead.current_status or "NEW",
        final_outcome=final_outcome,
        approach_summary=approach,
        conversation_summary=conv_summary,
        outcome_reason=outcome_reason,
        recommended_next_action=next_action,
        channels_used=channels,
        timeline=events,
    )


def _increment_counts(counts: IdeaReportSummaryCounts, outcome: LeadOutcome) -> None:
    match outcome:
        case LeadOutcome.INTERESTED:
            counts.interested += 1
        case LeadOutcome.NOT_INTERESTED:
            counts.not_interested += 1
        case LeadOutcome.FOLLOW_UP_REQUIRED:
            counts.follow_up_required += 1
        case LeadOutcome.CONVERTED:
            counts.converted += 1
        case LeadOutcome.NO_ANSWER:
            counts.no_answer += 1
        case LeadOutcome.NO_RESPONSE:
            counts.no_response += 1
        case LeadOutcome.DO_NOT_CONTACT:
            counts.do_not_contact += 1
        case LeadOutcome.FAILED:
            counts.failed += 1
        case LeadOutcome.CONTACTING:
            counts.contacting += 1
        case LeadOutcome.NEW:
            counts.new += 1
        case _:
            counts.new += 1
