import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import Channel, Direction, LeadOutcome, ReportStatus


class TimelineEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: Channel
    direction: Direction
    timestamp: datetime
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None
    content: str = ""
    duration_seconds: int | None = None
    outcome: str | None = None
    delivery_status: str | None = None


class LeadReportItemResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    lead_name: str
    company_website: str | None = None
    phone: str | None = None
    email: str | None = None
    final_outcome: LeadOutcome
    approach_summary: str
    conversation_summary: str
    outcome_reason: str
    recommended_next_action: str | None = None
    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None
    source_event_count: int = 0
    channels_used: list[Channel] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)


class IdeaReportSummaryCounts(BaseModel):
    total_leads: int = 0
    interested: int = 0
    not_interested: int = 0
    follow_up_required: int = 0
    converted: int = 0
    no_answer: int = 0
    no_response: int = 0
    do_not_contact: int = 0
    failed: int = 0
    contacting: int = 0
    new: int = 0


class IdeaReportRunResponse(BaseModel):
    id: uuid.UUID
    report_date: date
    status: ReportStatus
    total_leads: int = 0
    summary_counts: IdeaReportSummaryCounts = Field(default_factory=IdeaReportSummaryCounts)
    generated_at: datetime | None = None
    document_filename: str | None = None
    download_url: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[LeadReportItemResponse] = Field(default_factory=list)


class DailyReportGenerateRequest(BaseModel):
    report_date: date | None = None


class LeadJourneySummaryResponse(BaseModel):
    lead_id: uuid.UUID
    lead_name: str
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    current_status: str = "NEW"
    final_outcome: LeadOutcome
    approach_summary: str
    conversation_summary: str
    outcome_reason: str
    recommended_next_action: str | None = None
    channels_used: list[Channel] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
