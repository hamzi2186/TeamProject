import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base, GUID


class IdeaReportRun(Base):
    __tablename__ = "idea_report_runs"
    __table_args__ = (
        UniqueConstraint("report_date", name="uq_idea_report_runs_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING", index=True
    )
    total_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_path: Mapped[str | None] = mapped_column(Text)
    document_filename: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list["IdeaLeadReportItem"]] = relationship(
        "IdeaLeadReportItem",
        back_populates="report_run",
        cascade="all, delete-orphan",
        order_by="IdeaLeadReportItem.created_at",
    )


class IdeaLeadReportItem(Base):
    __tablename__ = "idea_lead_report_items"
    __table_args__ = (
        UniqueConstraint("report_run_id", "lead_id", name="uq_idea_lead_items_run_lead"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    report_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("idea_report_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, index=True
    )
    final_outcome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approach_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outcome_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommended_next_action: Mapped[str | None] = mapped_column(Text)
    first_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    report_run: Mapped["IdeaReportRun"] = relationship(
        "IdeaReportRun", back_populates="items"
    )
