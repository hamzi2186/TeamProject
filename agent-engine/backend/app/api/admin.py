from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin_or_internal_service
from app.db.session import get_db
from app.models.agent import AgentDocument
from app.schemas.agent import AgentDocumentSummary, IngestRequest, IngestResponse
from app.services.ingestion import AgentIngestionService

router = APIRouter(
    prefix="/api/v1/agent/admin",
    tags=["agent-admin"],
    dependencies=[Depends(require_admin_or_internal_service)],
)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documentation(
    payload: IngestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IngestResponse:
    service = AgentIngestionService(db)
    return await service.ingest(
        module_filter=payload.module_key,
        force=payload.force,
    )


@router.get("/sources", response_model=list[AgentDocumentSummary])
async def list_sources(
    db: Annotated[AsyncSession, Depends(get_db)],
    module_key: str | None = None,
) -> list[AgentDocumentSummary]:
    query = select(AgentDocument)
    if module_key:
        query = query.where(AgentDocument.module_key == module_key.strip().casefold())
    query = query.order_by(AgentDocument.module_key, AgentDocument.source_path)

    result = await db.execute(query)
    docs = result.scalars().all()

    return [
        AgentDocumentSummary(
            id=doc.id,
            module_key=doc.module_key,
            source_path=doc.source_path,
            file_name=doc.file_name,
            title=doc.title,
            version=doc.version,
            chunk_count=doc.chunk_count,
            active=doc.active,
            last_indexed_at=doc.last_indexed_at,
        )
        for doc in docs
    ]

