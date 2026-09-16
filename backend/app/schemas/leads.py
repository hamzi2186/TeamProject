from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hubspot_contact_id: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    phone: str | None
    email: str | None
    website_url: str | None
    website_id: UUID | None
    current_status: str
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    current_status: str | None = None
