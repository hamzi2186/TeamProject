#!/usr/bin/env python3
"""
Reconciliation tool: verifies that a persisted idea-engine daily report (DB rows +
generated DOCX) exactly matches the raw interaction tables in the shared database.

It reuses the exact same code paths the report pipeline uses
(`fetch_lead_events`, `evaluate_lead_outcome`, `fetch_lead_campaign_names`,
`get_report_detail`) so any drift between raw data and the report is caught.

Checks per lead item:
  - source_event_count == number of raw events
  - first_activity_at / last_activity_at == min/max raw event timestamps
  - channels_used == channels observed in raw events
  - campaigns == campaign names resolved from raw conversations/calls
  - final_outcome == outcome re-evaluated from raw events
  - DOCX info row (status, campaigns, touchpoint count, first/last touch) matches
  - every raw event signature (timestamp + channel + direction + sender) appears
    in the DOCX event-log table, with no extras

Usage:
  python3 scripts/verify_report_against_raw.py
  python3 scripts/verify_report_against_raw.py --report-date 2026-09-18
  python3 scripts/verify_report_against_raw.py --report-id <uuid>
"""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

# Allow running directly from the repo root or from idea-engine/backend
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.idea_reports import IdeaReportRun
from app.models.shared_reads import LeadRead
from app.services.aggregator import fetch_lead_campaign_names, fetch_lead_events
from app.services.outcome_evaluator import evaluate_lead_outcome
from app.services.report_service import get_report_detail

PASS, FAIL = "PASS", "FAIL"


def docx_ts(event) -> str:
    return event.timestamp.strftime("%Y-%m-%d %H:%M:%S") if event.timestamp else "N/A"


def event_signature(event) -> tuple:
    return (
        docx_ts(event),
        event.channel.value if event.channel else "N/A",
        event.direction.value if event.direction else "N/A",
        event.sender or "-",
    )


def extract_docx_from_path(path: Path):
    from docx import Document

    doc = Document(str(path))
    info_records, event_rows = [], []
    for table in doc.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        if rows and rows[0] and rows[0][0] == "Time (UTC)":
            for row in rows[1:]:
                event_rows.append(tuple(row[:4]))
            continue
        texts = [cell for row in rows for cell in row]
        if any(t.startswith("Email: ") for t in texts):
            rec = {}
            for t in texts:
                key = t.split(":", 1)[0]
                if t.startswith("Campaigns: "):
                    rec["campaigns"] = t[len("Campaigns: "):]
                elif t.startswith("Total Touchpoints: "):
                    rec["touchpoints"] = t[len("Total Touchpoints: "):]
                elif t.startswith("Current Status: "):
                    rec["status"] = t[len("Current Status: "):]
                elif t.startswith("First Touch: "):
                    rec["first_touch"] = t[len("First Touch: "):]
                elif t.startswith("Last Touch: "):
                    rec["last_touch"] = t[len("Last Touch: "):]
            if rec:
                info_records.append(rec)
    return info_records, event_rows


async def verify(report_id: str | None, report_date: str | None) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    failures = 0

    async with session_factory() as session:
        if report_id:
            stmt = select(IdeaReportRun).where(IdeaReportRun.id == report_id)
        elif report_date:
            _parsed = date.fromisoformat(report_date)
            stmt = select(IdeaReportRun).where(IdeaReportRun.report_date == _parsed)
        else:
            stmt = (
                select(IdeaReportRun)
                .where(IdeaReportRun.status == "COMPLETED")
                .order_by(desc(IdeaReportRun.report_date))
            )
        run = (await session.execute(stmt.limit(1))).scalar_one_or_none() if not report_id else (
            await session.execute(stmt)
        ).scalar_one_or_none()
        if not run:
            print("No report run found for the given criteria.")
            await engine.dispose()
            return 1

        dto = await get_report_detail(session, run.id)
        print(f"Report: {dto.report_date} ({dto.id}) - status={dto.status.value}, leads={dto.total_leads}")

        doc_path = None
        if run.document_path and Path(run.document_path).exists():
            doc_path = Path(run.document_path)
        else:
            cand = Path(settings.reports_storage_dir) / (run.document_filename or "")
            if cand.exists():
                doc_path = cand
        if not doc_path:
            print("FAIL: DOCX not found on disk for this report run.")
            await engine.dispose()
            return 1
        print(f"DOCX: {doc_path}")

        info_records, doc_events = extract_docx_from_path(doc_path)

        expected_all_signatures = []
        for idx, item in enumerate(dto.items):
            lead = (
                await session.execute(select(LeadRead).where(LeadRead.id == item.lead_id))
            ).scalar_one_or_none()
            events = await fetch_lead_events(session, item.lead_id)
            expected_campaigns = await fetch_lead_campaign_names(session, item.lead_id)
            expected_outcome, _, _ = evaluate_lead_outcome(
                events=events,
                persisted_outcome=lead.current_status if lead else None,
                current_status=lead.current_status if lead else None,
            )
            expected_channels = sorted({e.channel for e in events}, key=lambda c: c.value)
            expected_first = min((e.timestamp for e in events), default=None)
            expected_last = max((e.timestamp for e in events), default=None)
            expected_all_signatures.extend(event_signature(e) for e in events)

            checks = {
                "source_event_count": (item.source_event_count == len(events),
                                       f"stored={item.source_event_count} raw={len(events)}"),
                "first_activity_at": (item.first_activity_at == expected_first,
                                      f"stored={item.first_activity_at} raw={expected_first}"),
                "last_activity_at": (item.last_activity_at == expected_last,
                                     f"stored={item.last_activity_at} raw={expected_last}"),
                "channels_used": ([c.value for c in item.channels_used]
                                  == [c.value for c in expected_channels],
                                  f"stored={[c.value for c in item.channels_used]} raw={[c.value for c in expected_channels]}"),
                "campaigns": (sorted(item.campaigns or []) == sorted(expected_campaigns),
                              f"stored={item.campaigns or []} raw={expected_campaigns}"),
                "final_outcome": (item.final_outcome == expected_outcome,
                                  f"stored={item.final_outcome.value} raw={expected_outcome.value}"),
            }

            expected_camp_text = ", ".join(sorted(expected_campaigns)) if expected_campaigns else "None"
            expected_touch_text = str(len(events))
            expected_first_text = expected_first.strftime("%m/%d %H:%M") if expected_first else "N/A"
            expected_last_text = expected_last.strftime("%m/%d %H:%M") if expected_last else "N/A"
            rec = info_records[idx] if idx < len(info_records) else {}
            checks["docx_status"] = (rec.get("status") == item.final_outcome.value,
                                     f"docx={rec.get('status')} expected={item.final_outcome.value}")
            checks["docx_campaigns"] = (rec.get("campaigns") == expected_camp_text,
                                        f"docx={rec.get('campaigns')} expected={expected_camp_text}")
            checks["docx_touchpoints"] = (rec.get("touchpoints") == expected_touch_text,
                                          f"docx={rec.get('touchpoints')} expected={expected_touch_text}")
            checks["docx_first_touch"] = (rec.get("first_touch") == expected_first_text,
                                          f"docx={rec.get('first_touch')} expected={expected_first_text}")
            checks["docx_last_touch"] = (rec.get("last_touch") == expected_last_text,
                                         f"docx={rec.get('last_touch')} expected={expected_last_text}")

            head = f"[{idx + 1}] {item.lead_name}"
            failed_checks = [k for k, (ok, _) in checks.items() if not ok]
            if failed_checks:
                failures += 1
                print(f"{FAIL} {head}")
                for k, (ok, detail) in checks.items():
                    if not ok:
                        print(f"      {k}: {detail}")
            else:
                print(f"{PASS} {head} -> {item.final_outcome.value} ({len(events)} events)")

        doc_signature_set = set(doc_events)
        expected_set = set(expected_all_signatures)
        missing = expected_set - doc_signature_set
        extras = doc_signature_set - expected_set
        n_doc_events = len(doc_events)
        if missing or extras:
            failures += 1
            print(f"{FAIL} DOCX event-log coverage: {n_doc_events} rows, "
                  f"{len(expected_all_signatures)} raw events")
            if missing:
                print(f"      missing from DOCX: {len(missing)} signatures")
            if extras:
                print(f"      extra in DOCX: {len(extras)} signatures")
        else:
            print(f"{PASS} DOCX event-log coverage: {n_doc_events} rows == {len(expected_all_signatures)} raw events")

        print(f"\n{'FAIL' if failures else 'PASS'} overall: reconnected {len(dto.items)} lead items "
              f"against raw tables and {doc_path.name}")

    await engine.dispose()
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify daily report against raw interaction tables")
    parser.add_argument("--report-id", help="IdeaReportRun UUID to verify")
    parser.add_argument("--report-date", help="Report date (YYYY-MM-DD) to verify")
    args = parser.parse_args()
    sys.exit(asyncio.run(verify(args.report_id, args.report_date)))