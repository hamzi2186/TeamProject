import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hubspot import HubSpotConnection
from app.models.lead import Lead
from app.schemas.hubspot import NormalizedHubSpotContact
from app.schemas.leads import LeadUpdate


@dataclass(frozen=True)
class ImportCounts:
    imported: int
    created: int
    updated: int


def contact_to_lead_values(
    contact: NormalizedHubSpotContact,
    *,
    user_id: UUID,
    connection_id: UUID,
) -> dict:
    first_name = contact.firstname.strip() if contact.firstname else None
    last_name = contact.lastname.strip() if contact.lastname else None
    display_name = " ".join(value for value in (first_name, last_name) if value) or None
    return {
        "user_id": user_id,
        "hubspot_connection_id": connection_id,
        "hubspot_contact_id": contact.provider_contact_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
        "phone": contact.phone,
        "email": contact.email,
        "website_url": contact.website,
        "current_status": "new",
        "source_payload": {
            "provider": "hubspot",
            "contact": contact.model_dump(),
        },
    }


class LeadRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def connection_id(self, user_id: UUID, portal_id: str) -> UUID | None:
        return await self._db.scalar(
            select(HubSpotConnection.id).where(
                HubSpotConnection.user_id == user_id,
                HubSpotConnection.hubspot_portal_id == portal_id,
            )
        )

    async def upsert_contacts(
        self,
        *,
        user_id: UUID,
        connection_id: UUID,
        contacts: list[NormalizedHubSpotContact],
    ) -> ImportCounts:
        contact_ids = [contact.provider_contact_id for contact in contacts]
        existing = set(
            (
                await self._db.scalars(
                    select(Lead.hubspot_contact_id).where(
                        Lead.user_id == user_id,
                        Lead.hubspot_contact_id.in_(contact_ids),
                    )
                )
            ).all()
        )
        for contact in contacts:
            values = contact_to_lead_values(
                contact, user_id=user_id, connection_id=connection_id
            )
            statement = insert(Lead).values(id=uuid.uuid4(), **values)
            await self._db.execute(
                statement.on_conflict_do_update(
                    constraint="uq_leads_user_hubspot_contact",
                    set_={
                        **{
                            key: value
                            for key, value in values.items()
                            if key not in {"user_id", "hubspot_contact_id", "current_status"}
                        },
                        "updated_at": datetime.now(UTC),
                    },
                )
            )
        await self._db.commit()
        created = len(set(contact_ids) - existing)
        return ImportCounts(
            imported=len(contacts), created=created, updated=len(contacts) - created
        )

    async def list_for_user(self, user_id: UUID) -> list[Lead]:
        result = await self._db.scalars(
            select(Lead).where(Lead.user_id == user_id).order_by(Lead.updated_at.desc())
        )
        return list(result.all())

    async def get_for_user(self, user_id: UUID, lead_id: UUID) -> Lead | None:
        return await self._db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.user_id == user_id)
        )

    async def update_for_user(
        self, user_id: UUID, lead_id: UUID, changes: LeadUpdate
    ) -> Lead | None:
        lead = await self.get_for_user(user_id, lead_id)
        if lead is None:
            return None
        values = changes.model_dump(exclude_unset=True)
        if "current_status" in values and not values["current_status"]:
            values.pop("current_status")
        for key, value in values.items():
            setattr(lead, key, value)
        if "first_name" in values or "last_name" in values:
            lead.display_name = " ".join(
                value for value in (lead.first_name, lead.last_name) if value
            ) or None
        await self._db.commit()
        await self._db.refresh(lead)
        return lead

    async def set_lead_website(
        self, user_id: UUID, lead_id: UUID, website_id: UUID, website_url: str | None = None
    ) -> Lead | None:
        lead = await self.get_for_user(user_id, lead_id)
        if lead is None:
            return None
        lead.website_id = website_id
        if website_url:
            lead.website_url = website_url
        await self._db.commit()
        await self._db.refresh(lead)
        return lead
