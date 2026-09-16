from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HubSpotTokenSet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    expires_in: int = Field(gt=0)
    scopes: list[str] = Field(default_factory=list)


class NormalizedContact(BaseModel):
    provider_contact_id: str
    firstname: str | None = None
    lastname: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None


class ContactPage(BaseModel):
    contacts: list[NormalizedContact]
    next_after: str | None = None


class ConnectRequest(BaseModel):
    user_id: UUID


class ConnectResponse(BaseModel):
    authorization_url: str
    expires_in: int


class CallbackResponse(BaseModel):
    connected: bool
    status: str
    portal_id: str


class ConnectionStatusResponse(BaseModel):
    status: str
    connected: bool
    portal_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None


class ContactPageResponse(BaseModel):
    contacts: list[NormalizedContact]
    next_after: str | None = None
