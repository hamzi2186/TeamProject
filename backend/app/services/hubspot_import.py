from uuid import UUID

from app.schemas.hubspot import HubSpotImportRequest, NormalizedHubSpotContact
from app.services.leads import ImportCounts, LeadRepository
from app.services.tpi_hubspot import TPIHubSpotClient, TPIHubSpotError


class HubSpotImportService:
    def __init__(self, tpi: TPIHubSpotClient, leads: LeadRepository) -> None:
        self._tpi = tpi
        self._leads = leads

    async def run(self, user_id: UUID, selection: HubSpotImportRequest) -> ImportCounts:
        status = await self._tpi.status(user_id)
        if not status.connected or not status.portal_id:
            raise TPIHubSpotError("HubSpot is not connected", 409)
        connection_id = await self._leads.connection_id(user_id, status.portal_id)
        if connection_id is None:
            raise TPIHubSpotError("HubSpot connection metadata is unavailable", 409)

        wanted = set(selection.hubspot_contact_ids)
        selected: list[NormalizedHubSpotContact] = []
        after: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page = await self._tpi.contacts(user_id, after=after, limit=100)
            if selection.select_all:
                selected.extend(page.contacts)
            else:
                selected.extend(
                    contact for contact in page.contacts if contact.provider_contact_id in wanted
                )
                found = {contact.provider_contact_id for contact in selected}
                if found == wanted:
                    break
            if not page.next_after:
                break
            if page.next_after in seen_cursors:
                raise TPIHubSpotError("HubSpot pagination returned a repeated cursor")
            seen_cursors.add(page.next_after)
            after = page.next_after
        if not selection.select_all:
            found = {contact.provider_contact_id for contact in selected}
            if found != wanted:
                raise TPIHubSpotError("One or more selected HubSpot contacts were not found", 404)
        selected = list(
            {contact.provider_contact_id: contact for contact in selected}.values()
        )
        return await self._leads.upsert_contacts(
            user_id=user_id, connection_id=connection_id, contacts=selected
        )
