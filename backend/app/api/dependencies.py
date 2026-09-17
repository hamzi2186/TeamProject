from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.hubspot_import import HubSpotImportService
from app.services.leads import LeadRepository
from app.services.scraper_client import ScraperClient, get_scraper_client
from app.services.tpi_hubspot import TPIHubSpotClient, get_tpi_hubspot_client


def get_lead_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeadRepository:
    return LeadRepository(db)


def get_hubspot_import_service(
    tpi: Annotated[TPIHubSpotClient, Depends(get_tpi_hubspot_client)],
    leads: Annotated[LeadRepository, Depends(get_lead_repository)],
    scraper: Annotated[ScraperClient, Depends(get_scraper_client)],
) -> HubSpotImportService:
    return HubSpotImportService(tpi, leads, scraper)

