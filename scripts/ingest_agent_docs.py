"""CLI script for ingesting agent product documentation into the Agent Knowledge Base."""
import argparse
import asyncio
import sys
from pathlib import Path

# Add agent-engine backend to sys.path
repo_root = Path(__file__).resolve().parents[1]
agent_backend = repo_root / "agent-engine" / "backend"
sys.path.insert(0, str(agent_backend))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.services.discovery import DocumentDiscoveryService  # noqa: E402
from app.services.ingestion import AgentIngestionService  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest documentation into T Rex Agent Knowledge Base"
    )
    parser.add_argument(
        "--module",
        "-m",
        type=str,
        default=None,
        help="Optional module filter (e.g. 'scraper', 'calling', 'sms')",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-indexing even if document content hash has not changed",
    )
    parser.add_argument(
        "--docs-root",
        type=str,
        default=None,
        help="Custom docs root path (defaults to repo docs/agent-knowledge)",
    )
    args = parser.parse_args()

    settings = get_settings()
    docs_root = Path(args.docs_root) if args.docs_root else (repo_root / "docs" / "agent-knowledge")

    print("=" * 60)
    print("T REX AGENT KNOWLEDGE BASE INGESTION")
    print("=" * 60)
    print(f"Docs Root Path:   {docs_root}")
    print(f"Module Filter:    {args.module or 'ALL'}")
    print(f"Force Re-index:   {args.force}")
    print(f"TPI Base URL:     {settings.tpi_api_base_url}")
    print(f"Embedding Space:  {settings.embedding_provider}/{settings.embedding_model} ({settings.embedding_dimension}d)")
    print("-" * 60)

    if not docs_root.exists():
        print(f"ERROR: Docs root path does not exist: {docs_root}")
        return 1

    discovery = DocumentDiscoveryService(docs_root)

    async with SessionLocal() as db:
        service = AgentIngestionService(
            db=db,
            discovery_service=discovery,
            settings=settings,
        )
        try:
            res = await service.ingest(module_filter=args.module, force=args.force)
        except Exception as exc:
            print(f"ERROR: Ingestion failed: {exc}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            await engine.dispose()

    print("\nINGESTION SUMMARY:")
    print(f"  Scanned:         {res.scanned}")
    print(f"  Created:         {res.created}")
    print(f"  Updated:         {res.updated}")
    print(f"  Unchanged:       {res.unchanged}")
    print(f"  Deactivated:     {res.deactivated}")
    print(f"  Chunks Indexed:  {res.chunks_indexed}")
    print("-" * 60)

    if res.details:
        print("DETAILS:")
        for item in res.details:
            title_part = f" ('{item.title}')" if item.title else ""
            print(f"  [{item.status.upper():<11}] {item.source_path}{title_part} -> {item.chunk_count} chunks")

    print("=" * 60)
    print("Ingestion completed successfully.")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

