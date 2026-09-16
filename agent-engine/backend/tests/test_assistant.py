import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.schemas.agent import AgentSearchResponse, AgentSearchResultItem
from app.services.assistant import FALLBACK_ANSWER, AgentAssistantService
from app.services.retrieval import AgentRetrievalService
from app.services.tpi_client import LLMGenerationResult, TPILlmClient, TPILlmError


def make_chunk_item(
    *,
    module_key: str = "scraper",
    source_path: str = "scraper/overview.md",
    header_path: str = "Overview",
    content: str = "Scraper engine crawls websites.",
    similarity: float = 0.85,
) -> AgentSearchResultItem:
    return AgentSearchResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        module_key=module_key,
        source_path=source_path,
        file_name="overview.md",
        title="Overview",
        header_path=header_path,
        content=content,
        similarity=similarity,
        metadata={},
    )


@pytest.mark.asyncio
async def test_assistant_orchestration_success():
    db = AsyncMock()
    mock_retrieval = AsyncMock(spec=AgentRetrievalService)
    mock_llm = AsyncMock(spec=TPILlmClient)

    chunk1 = make_chunk_item(similarity=0.88)
    chunk2 = make_chunk_item(
        source_path="scraper/workflow.md",
        header_path="Workflow",
        content="Workflow details.",
        similarity=0.76,
    )
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="How does scraper work?",
        module_filter=None,
        total=2,
        items=[chunk1, chunk2],
    )

    mock_llm.generate.return_value = LLMGenerationResult(
        text="The scraper crawls websites and builds a knowledge base.",
        provider="groq",
        model="llama-3.3-70b-versatile",
        input_tokens=150,
        output_tokens=40,
    )

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="service-token",
        agent_assistant_top_k=5,
        agent_assistant_min_similarity=0.5,
        agent_assistant_context_max_chars=8000,
    )

    service = AgentAssistantService(
        db=db,
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        settings=settings,
    )

    response = await service.ask("How does scraper work?")

    assert response.answer == "The scraper crawls websites and builds a knowledge base."
    assert len(response.sources) == 2
    assert response.sources[0].source_path == "scraper/overview.md"
    assert response.sources[0].similarity == 0.88
    assert response.sources[1].source_path == "scraper/workflow.md"
    assert response.sources[1].similarity == 0.76
    assert response.generation is not None
    assert response.generation.provider == "groq"
    assert response.generation.model == "llama-3.3-70b-versatile"
    assert response.generation.input_tokens == 150
    assert response.generation.output_tokens == 40

    assert mock_retrieval.search.call_count == 1
    assert mock_llm.generate.call_count == 1


@pytest.mark.asyncio
async def test_assistant_no_chunks_returns_fallback_without_calling_llm():
    db = AsyncMock()
    mock_retrieval = AsyncMock(spec=AgentRetrievalService)
    mock_llm = AsyncMock(spec=TPILlmClient)

    mock_retrieval.search.return_value = AgentSearchResponse(
        query="Quantum computing?",
        module_filter=None,
        total=0,
        items=[],
    )

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="service-token",
    )

    service = AgentAssistantService(
        db=db,
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        settings=settings,
    )

    response = await service.ask("Quantum computing?")

    assert response.answer == FALLBACK_ANSWER
    assert len(response.sources) == 0
    assert response.generation is None
    assert mock_llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_assistant_low_similarity_chunks_returns_fallback_without_llm():
    db = AsyncMock()
    mock_retrieval = AsyncMock(spec=AgentRetrievalService)
    mock_llm = AsyncMock(spec=TPILlmClient)

    # All chunks have similarity 0.35, below default 0.5 threshold
    chunk = make_chunk_item(similarity=0.35)
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="Unrelated query",
        module_filter=None,
        total=1,
        items=[chunk],
    )

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="service-token",
        agent_assistant_min_similarity=0.5,
    )

    service = AgentAssistantService(
        db=db,
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        settings=settings,
    )

    response = await service.ask("Unrelated query")

    assert response.answer == FALLBACK_ANSWER
    assert len(response.sources) == 0
    assert response.generation is None
    assert mock_llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_assistant_context_bounding():
    db = AsyncMock()
    mock_retrieval = AsyncMock(spec=AgentRetrievalService)
    mock_llm = AsyncMock(spec=TPILlmClient)

    # 3 chunks, each ~200 chars
    chunk1 = make_chunk_item(content="A" * 150, similarity=0.9)
    chunk2 = make_chunk_item(content="B" * 150, similarity=0.85)
    chunk3 = make_chunk_item(content="C" * 150, similarity=0.8)

    mock_retrieval.search.return_value = AgentSearchResponse(
        query="Test query",
        module_filter=None,
        total=3,
        items=[chunk1, chunk2, chunk3],
    )

    mock_llm.generate.return_value = LLMGenerationResult(
        text="Answer",
        provider="groq",
        model="llama-3.3-70b-versatile",
        input_tokens=10,
        output_tokens=5,
    )

    # Max chars 250 -> only chunk1 fits, chunk2 and chunk3 omitted
    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="service-token",
        agent_assistant_context_max_chars=250,
    )

    service = AgentAssistantService(
        db=db,
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        settings=settings,
    )

    response = await service.ask("Test query")

    assert response.answer == "Answer"
    assert len(response.sources) == 1
    assert response.sources[0].similarity == 0.9


@pytest.mark.asyncio
async def test_assistant_handles_tpi_failure():
    db = AsyncMock()
    mock_retrieval = AsyncMock(spec=AgentRetrievalService)
    mock_llm = AsyncMock(spec=TPILlmClient)

    chunk = make_chunk_item(similarity=0.8)
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="Query",
        module_filter=None,
        total=1,
        items=[chunk],
    )

    mock_llm.generate.side_effect = TPILlmError("LLM unavailable", retryable=True)

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="service-token",
    )

    service = AgentAssistantService(
        db=db,
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        settings=settings,
    )

    with pytest.raises(TPILlmError) as exc_info:
        await service.ask("Query")
    assert "LLM unavailable" in str(exc_info.value)
