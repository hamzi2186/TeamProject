import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def configure_root_backend() -> None:
    for key, value in dotenv_values(BACKEND / ".env").items():
        if value is not None:
            os.environ.setdefault(key, value)
    os.environ["AUTH_JWT_PRIVATE_KEY_PATH"] = str(
        BACKEND / ".secrets" / "auth_private.pem"
    )
    os.environ["AUTH_JWT_PUBLIC_KEY_PATH"] = str(
        BACKEND / ".secrets" / "auth_public.pem"
    )
    sys.path.insert(0, str(BACKEND))


async def acceptance_users():
    from sqlalchemy import select

    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.models.auth import AppUser

    async with SessionLocal() as db:
        users = []
        for label in ("a", "b"):
            email = f"scraper.acceptance.{label}@example.test"
            user = await db.scalar(select(AppUser).where(AppUser.email == email))
            if user is None:
                user = AppUser(email=email, role="customer")
                db.add(user)
                await db.flush()
            users.append(user)
        await db.commit()
        return tuple(
            (user.id, create_access_token(user.id, user.role)[0]) for user in users
        )


async def database_counts(user_id, knowledge_base_id):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        row = (
            await db.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM web_pages WHERE user_id=:user_id) AS pages, "
                    "(SELECT count(*) FROM kb_chunks WHERE user_id=:user_id "
                    "AND knowledge_base_id=:kb_id) AS chunks, "
                    "(SELECT count(*) FROM kb_chunks WHERE user_id=:user_id "
                    "AND knowledge_base_id=:kb_id AND embedding_dimension=1024) AS vectors"
                ),
                {"user_id": user_id, "kb_id": knowledge_base_id},
            )
        ).one()
        return {"pages": row.pages, "chunks": row.chunks, "vectors": row.vectors}


async def main() -> None:
    configure_root_backend()
    (
        (tenant_a_id, tenant_a_token),
        (tenant_b_id, tenant_b_token),
    ) = await acceptance_users()
    async with httpx.AsyncClient(
        base_url="http://localhost:8002", timeout=45, trust_env=False
    ) as client:
        headers_a = {"Authorization": f"Bearer {tenant_a_token}"}
        headers_b = {"Authorization": f"Bearer {tenant_b_token}"}
        ingest = await client.post(
            "/api/v1/websites/ingest",
            headers=headers_a,
            json={"url": "https://www.owenclinic.net/", "lead_ids": []},
        )
        ingest.raise_for_status()
        submitted = ingest.json()
        website_id = submitted["website"]["id"]
        kb_id = submitted["knowledge_base_id"]
        job_id = submitted["job_id"]

        deadline = time.monotonic() + 900
        state = None
        while job_id and time.monotonic() < deadline:
            try:
                response = await client.get(
                    f"/api/v1/scrape-jobs/{job_id}", headers=headers_a
                )
                if response.status_code >= 500:
                    await asyncio.sleep(3)
                    continue
                response.raise_for_status()
                state = response.json()
                if state["status"] in {"COMPLETED", "PARTIAL", "FAILED"}:
                    break
            except httpx.HTTPError:
                await asyncio.sleep(3)
                continue
            await asyncio.sleep(3)
        if job_id and (
            state is None or state["status"] not in {"COMPLETED", "PARTIAL"}
        ):
            raise RuntimeError(f"Scrape job did not complete: {state}")

        website = (
            await client.get(f"/api/v1/websites/{website_id}", headers=headers_a)
        ).json()
        pages = (
            await client.get(f"/api/v1/websites/{website_id}/pages", headers=headers_a)
        ).json()
        query_text = "What services and care does Owen Clinic provide?"
        retrieval = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/search",
            headers=headers_a,
            json={"query": query_text, "top_k": 6},
        )
        retrieval.raise_for_status()
        results = retrieval.json()
        before_repeat = await database_counts(tenant_a_id, kb_id)

        repeat = await client.post(
            "/api/v1/websites/ingest",
            headers=headers_a,
            json={"url": "http://owenclinic.net", "lead_ids": []},
        )
        repeat.raise_for_status()
        repeated = repeat.json()
        after_repeat = await database_counts(tenant_a_id, kb_id)
        assert repeated["website"]["id"] == website_id
        assert repeated["knowledge_base_id"] == kb_id
        assert repeated["reused"] is True
        assert before_repeat == after_repeat

        denied_get = await client.get(
            f"/api/v1/websites/{website_id}", headers=headers_b
        )
        denied_search = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/search",
            headers=headers_b,
            json={"query": "private tenant content", "top_k": 6},
        )
        assert denied_get.status_code == 404
        assert denied_search.status_code == 404

    evidence = {
        "website": "https://www.owenclinic.net/",
        "normalized_url": website["normalized_url"],
        "job_id": job_id,
        "job_state": state["status"] if state else "REUSED_READY",
        "knowledge_base_id": kb_id,
        "kb_state": website["kb_status"],
        "pages_discovered": state["pages_discovered"] if state else len(pages),
        "pages_indexed": website["page_count"],
        "chunks_generated": website["chunk_count"],
        "embedding_provider": results["embedding_provider"],
        "embedding_model": results["embedding_model"],
        "embedding_dimension": results["embedding_dimension"],
        "vectors_persisted": before_repeat["vectors"],
        "retrieval_query": query_text,
        "retrieval_result_count": len(results["results"]),
        "source_urls": sorted({item["source_url"] for item in results["results"]}),
        "repeat_reused": repeated["reused"],
        "repeat_counts_unchanged": before_repeat == after_repeat,
        "tenant_a": str(tenant_a_id),
        "tenant_b": str(tenant_b_id),
        "tenant_b_website_status": denied_get.status_code,
        "tenant_b_retrieval_status": denied_search.status_code,
    }
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
