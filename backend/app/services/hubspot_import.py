import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.schemas.hubspot import (
    HubSpotImportRequest,
    HubSpotWebsiteIngestionFailure,
    NormalizedHubSpotContact,
)
from app.services.leads import LeadRepository
from app.services.scraper_client import ScraperClient, ScraperClientError
from app.services.tpi_hubspot import TPIHubSpotClient, TPIHubSpotError


SCRAPER_INGEST_LEAD_LIMIT = 500
SCRAPER_INGEST_CONCURRENCY = 8


@dataclass(frozen=True)
class HubSpotImportResult:
    imported: int
    created: int
    updated: int
    website_ingestion_failures: list[HubSpotWebsiteIngestionFailure]


class HubSpotImportService:
    def __init__(
        self, tpi: TPIHubSpotClient, leads: LeadRepository, scraper: ScraperClient
    ) -> None:
        self._tpi = tpi
        self._leads = leads
        self._scraper = scraper

    async def run(
        self, user_id: UUID, role: str, selection: HubSpotImportRequest
    ) -> HubSpotImportResult:
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
        counts = await self._leads.upsert_contacts(
            user_id=user_id, connection_id=connection_id, contacts=selected
        )
        failures = await self._ingest_websites(user_id, role, selected)
        return HubSpotImportResult(
            imported=counts.imported,
            created=counts.created,
            updated=counts.updated,
            website_ingestion_failures=failures,
        )

    async def _ingest_websites(
        self, user_id: UUID, role: str, contacts: list[NormalizedHubSpotContact]
    ) -> list[HubSpotWebsiteIngestionFailure]:
        contact_ids = [contact.provider_contact_id for contact in contacts]
        lead_ids = await self._leads.lead_ids_by_hubspot_contact(user_id, contact_ids)
        raw_groups: dict[str, list[tuple[str, UUID]]] = {}
        for contact in contacts:
            website_url = (contact.website or "").strip()
            lead_id = lead_ids.get(contact.provider_contact_id)
            if website_url and lead_id:
                raw_groups.setdefault(website_url, []).append(
                    (contact.provider_contact_id, lead_id)
                )

        semaphore = asyncio.Semaphore(SCRAPER_INGEST_CONCURRENCY)

        async def normalize_group(website_url: str, entries: list[tuple[str, UUID]]):
            async with semaphore:
                try:
                    normalized = await self._scraper.normalize_website(
                        user_id, role, website_url
                    )
                except ScraperClientError as exc:
                    return None, None, entries, HubSpotWebsiteIngestionFailure(
                        hubspot_contact_ids=[contact_id for contact_id, _ in entries],
                        message=str(exc),
                    )
            return (
                normalized["normalized_key"],
                normalized["normalized_url"],
                entries,
                None,
            )

        normalized_groups = await asyncio.gather(
            *(normalize_group(url, entries) for url, entries in raw_groups.items())
        )
        failures = [result[3] for result in normalized_groups if result[3] is not None]
        canonical_groups: dict[str, tuple[str, list[tuple[str, UUID]]]] = {}
        for normalized_key, normalized_url, entries, failure in normalized_groups:
            if failure is not None:
                continue
            _, canonical_entries = canonical_groups.setdefault(
                normalized_key, (normalized_url, [])
            )
            canonical_entries.extend(entries)

        async def ingest_site(
            normalized_url: str, entries: list[tuple[str, UUID]]
        ) -> list[HubSpotWebsiteIngestionFailure]:
            site_failures = []
            for index in range(0, len(entries), SCRAPER_INGEST_LEAD_LIMIT):
                batch = entries[index : index + SCRAPER_INGEST_LEAD_LIMIT]
                async with semaphore:
                    try:
                        await self._scraper.ingest_website(
                            user_id,
                            role,
                            url=normalized_url,
                            lead_ids=[lead_id for _, lead_id in batch],
                        )
                    except ScraperClientError as exc:
                        site_failures.append(
                            HubSpotWebsiteIngestionFailure(
                                hubspot_contact_ids=[contact_id for contact_id, _ in batch],
                                message=str(exc),
                            )
                        )
            return site_failures

        ingest_outcomes = await asyncio.gather(
            *(
                ingest_site(normalized_url, entries)
                for normalized_url, entries in canonical_groups.values()
            )
        )
        failures.extend(failure for outcome in ingest_outcomes for failure in outcome)
        return failures
