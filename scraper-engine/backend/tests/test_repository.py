from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.repositories.scraper import ScraperRepository


def fake_db(*, scalar_values=()):
    return SimpleNamespace(
        scalar=AsyncMock(side_effect=scalar_values),
        scalars=AsyncMock(),
        execute=AsyncMock(),
        commit=AsyncMock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        add=Mock(),
        add_all=Mock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("partial_reason", "expected_status", "expected_job_status"),
    [
        (None, "READY", "COMPLETED"),
        ("Crawl page limit reached", "PARTIAL", "PARTIAL"),
    ],
)
async def test_replace_index_persists_computed_completion_status(
    partial_reason, expected_status, expected_job_status
):
    db = fake_db()
    repository = ScraperRepository(db)
    job = SimpleNamespace(
        status="RUNNING",
        pages_indexed=0,
        chunks_generated=0,
        partial_reason=None,
        completed_at=None,
    )
    website = SimpleNamespace(
        id=uuid4(),
        crawl_status="CRAWLING",
        last_crawled_at=None,
        content_fingerprint=None,
    )
    kb = SimpleNamespace(
        id=uuid4(),
        status="PROCESSING",
        embedding_provider=None,
        embedding_model=None,
        embedding_dimension=None,
        page_count=0,
        chunk_count=0,
        last_error="old error",
    )

    await repository.replace_index(
        job=job,
        website=website,
        kb=kb,
        pages=[],
        chunks=[],
        provider="jina",
        model="jina-embeddings-v3",
        dimension=1024,
        content_fingerprint="fingerprint",
        partial_reason=partial_reason,
    )

    assert kb.status == expected_status
    assert website.crawl_status == expected_status
    assert job.status == expected_job_status
    assert job.partial_reason == partial_reason
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("kb_status", ["READY", "PARTIAL"])
async def test_ready_or_partial_kb_is_reused_without_new_job(kb_status):
    user_id = uuid4()
    website = SimpleNamespace(id=uuid4())
    kb = SimpleNamespace(id=uuid4(), status=kb_status)
    db = fake_db(scalar_values=(website, kb, None))
    repository = ScraperRepository(db)

    saved_website, saved_kb, job, reused = await repository.create_site_kb_job(
        user_id=user_id,
        original_url="https://example.com",
        normalized_url="https://example.com/",
        normalized_key="example.com",
        lead_ids=[],
    )

    assert saved_website is website
    assert saved_kb is kb
    assert job is None
    assert reused is True
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_active_job_is_reused_without_new_job():
    user_id = uuid4()
    website = SimpleNamespace(id=uuid4())
    kb = SimpleNamespace(id=uuid4(), status="PENDING")
    active_job = SimpleNamespace(id=uuid4(), status="QUEUED")
    db = fake_db(scalar_values=(website, kb, active_job))
    repository = ScraperRepository(db)

    _, _, job, reused = await repository.create_site_kb_job(
        user_id=user_id,
        original_url="https://example.com",
        normalized_url="https://example.com/",
        normalized_key="example.com",
        lead_ids=[],
    )

    assert job is active_job
    assert reused is True
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_failure_marks_only_owned_undispatched_queued_job_failed():
    user_id = uuid4()
    job_id = uuid4()
    db = fake_db()
    repository = ScraperRepository(db)

    await repository.mark_dispatch_failed(user_id, job_id)

    statement = db.execute.await_args.args[0]
    sql = str(statement)
    params = statement.compile().params
    assert "scrape_jobs.id" in sql
    assert "scrape_jobs.user_id" in sql
    assert "scrape_jobs.status" in sql
    assert "scrape_jobs.celery_task_id IS NULL" in sql
    assert "FAILED" in params.values()
    assert "TASK_DISPATCH_FAILED" in params.values()
    assert "Website ingestion could not be queued" in params.values()
    db.commit.assert_awaited_once()
