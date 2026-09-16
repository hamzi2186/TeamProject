from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class HubSpotConnectResponse(BaseModel):
    authorization_url: str
    expires_in: int


class HubSpotConnectionStatus(BaseModel):
    status: str
    connected: bool
    portal_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None


class NormalizedHubSpotContact(BaseModel):
    provider_contact_id: str
    firstname: str | None = None
    lastname: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None


class HubSpotContactPage(BaseModel):
    contacts: list[NormalizedHubSpotContact]
    next_after: str | None = None


class HubSpotImportRequest(BaseModel):
    hubspot_contact_ids: list[str] = Field(default_factory=list)
    select_all: bool = False

    @model_validator(mode="after")
    def exactly_one_selection_mode(self):
        has_ids = bool(self.hubspot_contact_ids)
        if has_ids == self.select_all:
            raise ValueError("Choose contact IDs or select_all, but not both")
        self.hubspot_contact_ids = list(dict.fromkeys(self.hubspot_contact_ids))
        return self


class HubSpotImportResponse(BaseModel):
    imported: int
    created: int
    updated: int
