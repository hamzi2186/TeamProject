from uuid import UUID, uuid4

from sqlalchemy import Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lead_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="CALL")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)