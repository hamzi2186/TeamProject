import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.main import app
from app.models.agent import AgentConversation, AgentMessage
from app.repositories.conversations import AgentConversationRepository
from app.schemas.agent import AgentSearchResponse, AgentSearchResultItem
from app.services.assistant import AgentAssistantService
from app.services.retrieval import AgentRetrievalService
from app.services.tpi_client import LLMGenerationResult, TPILlmClient, TPILlmError


def create_test_user() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uuid.uuid4(), role="customer")


def create_other_user() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uuid.uuid4(), role="customer")


# ── Auth & Isolation Tests ──────────────────────────────────────────────────

def test_conversations_api_requires_auth():
    client = TestClient(app)
    c_id = uuid.uuid4()

    assert client.post("/api/v1/agent/conversations", json={}).status_code == 401
    assert client.get("/api/v1/agent/conversations").status_code == 401
    assert client.get(f"/api/v1/agent/conversations/{c_id}").status_code == 401
    assert client.patch(f"/api/v1/agent/conversations/{c_id}", json={"title": "test"}).status_code == 401
    assert client.delete(f"/api/v1/agent/conversations/{c_id}").status_code == 401
    assert client.post(f"/api/v1/agent/conversations/{c_id}/messages", json={"content": "hi"}).status_code == 401


def test_conversations_crud_endpoints(monkeypatch):
    user = create_test_user()
    other_user = create_other_user()

    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: user

    now = datetime.now(UTC)
    conv_id = uuid.uuid4()
    mock_conv = AgentConversation(
        id=conv_id,
        user_id=user.user_id,
        title="Initial Title",
        created_at=now,
        updated_at=now,
    )
    mock_conv.messages = []

    # Mock repository methods
    monkeypatch.setattr(
        AgentConversationRepository,
        "create_conversation",
        AsyncMock(return_value=mock_conv),
    )
    monkeypatch.setattr(
        AgentConversationRepository,
        "list_conversations",
        AsyncMock(return_value=[mock_conv]),
    )
    monkeypatch.setattr(
        AgentConversationRepository,
        "get_conversation",
        AsyncMock(side_effect=lambda cid, uid, **kwargs: mock_conv if uid == user.user_id and cid == conv_id else None),
    )
    monkeypatch.setattr(
        AgentConversationRepository,
        "update_title",
        AsyncMock(side_effect=lambda cid, uid, title: AgentConversation(id=cid, user_id=uid, title=title, created_at=now, updated_at=now) if uid == user.user_id else None),
    )
    monkeypatch.setattr(
        AgentConversationRepository,
        "delete_conversation",
        AsyncMock(side_effect=lambda cid, uid: True if uid == user.user_id and cid == conv_id else False),
    )

    client = TestClient(app)

    # 1. Create conversation
    res_create = client.post("/api/v1/agent/conversations", json={"title": "Initial Title"})
    assert res_create.status_code == 201
    assert res_create.json()["id"] == str(conv_id)

    # 2. List conversations
    res_list = client.get("/api/v1/agent/conversations")
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    # 3. Get own conversation
    res_get = client.get(f"/api/v1/agent/conversations/{conv_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == str(conv_id)

    # 4. Rename own conversation
    res_patch = client.patch(f"/api/v1/agent/conversations/{conv_id}", json={"title": "Renamed Title"})
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Renamed Title"

    # 5. Cross-user checks: switch user to other_user -> ALL return 404 (consistent 404)
    app.dependency_overrides[get_current_user] = lambda: other_user

    assert client.get(f"/api/v1/agent/conversations/{conv_id}").status_code == 404
    assert client.patch(f"/api/v1/agent/conversations/{conv_id}", json={"title": "Hacked"}).status_code == 404
    assert client.delete(f"/api/v1/agent/conversations/{conv_id}").status_code == 404

    # 6. Delete own conversation (restore user)
    app.dependency_overrides[get_current_user] = lambda: user
    res_del = client.delete(f"/api/v1/agent/conversations/{conv_id}")
    assert res_del.status_code == 204

    app.dependency_overrides.clear()


# ── Multi-Turn Service Orchestration Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_ask_in_conversation_success(monkeypatch):
    user = create_test_user()
    conv_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_conv = AgentConversation(
        id=conv_id,
        user_id=user.user_id,
        title=None,
        created_at=now,
        updated_at=now,
    )
    mock_conv.messages = []

    mock_repo = AsyncMock()
    mock_repo.get_conversation.return_value = mock_conv
    mock_repo.get_recent_messages.return_value = []
    mock_repo.update_title.return_value = mock_conv
    mock_repo.touch_updated_at.return_value = None

    def fake_create_msg(conversation_id, role, content, sources=None, generation=None):
        return AgentMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            generation=generation,
            created_at=now,
        )

    mock_repo.create_message.side_effect = fake_create_msg

    # Mock retrieval
    mock_retrieval = AsyncMock()
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="How does scraper work?",
        module_filter=None,
        total=1,
        items=[
            AgentSearchResultItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                module_key="scraper",
                source_path="scraper/overview.md",
                file_name="overview.md",
                header_path="Overview",
                content="Scraper engine builds a knowledge base.",
                similarity=0.88,
            )
        ],
    )

    # Mock LLM
    captured_prompts = []
    mock_llm = AsyncMock()
    async def fake_generate(**kwargs):
        captured_prompts.append(kwargs)
        return LLMGenerationResult(
            text="The scraper engine builds a knowledge base from websites.",
            provider="groq",
            model="qwen/qwen3.8-27b",
            input_tokens=150,
            output_tokens=25,
        )
    mock_llm.generate.side_effect = fake_generate

    service = AgentAssistantService(
        db=AsyncMock(),
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        conversation_repo=mock_repo,
    )

    response = await service.ask_in_conversation(
        conversation_id=conv_id,
        user_id=user.user_id,
        question="How does scraper work?",
    )

    assert response.conversation_id == conv_id
    assert response.user_message.role == "user"
    assert response.user_message.content == "How does scraper work?"
    assert response.assistant_message.role == "assistant"
    assert "scraper engine builds a knowledge base" in response.assistant_message.content
    assert len(response.assistant_message.sources) == 1
    assert response.assistant_message.sources[0].source_path == "scraper/overview.md"
    assert response.assistant_message.generation.provider == "groq"

    # Verify title was derived from first question
    mock_repo.update_title.assert_called_once_with(conv_id, user.user_id, "How does scraper work?")
    # Verify current question is not duplicated in prompt
    assert len(captured_prompts) == 1
    user_prompt = captured_prompts[0]["user_prompt"]
    assert user_prompt.count("How does scraper work?") == 1


@pytest.mark.asyncio
async def test_ask_in_conversation_cross_user_fails_404():
    user = create_test_user()
    other_user = create_other_user()
    conv_id = uuid.uuid4()

    mock_repo = AsyncMock()
    # Conversation exists, but belongs to user, not other_user
    mock_repo.get_conversation.return_value = None

    service = AgentAssistantService(
        db=AsyncMock(),
        conversation_repo=mock_repo,
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.ask_in_conversation(
            conversation_id=conv_id,
            user_id=other_user.user_id,
            question="What is this?",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_ask_in_conversation_no_context_fallback_persists_and_skips_llm():
    user = create_test_user()
    conv_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_conv = AgentConversation(
        id=conv_id,
        user_id=user.user_id,
        title="Existing Conv",
        created_at=now,
        updated_at=now,
    )

    mock_repo = AsyncMock()
    mock_repo.get_conversation.return_value = mock_conv
    mock_repo.get_recent_messages.return_value = []
    mock_repo.touch_updated_at.return_value = None

    def fake_create_msg(conversation_id, role, content, sources=None, generation=None):
        return AgentMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            generation=generation,
            created_at=now,
        )

    mock_repo.create_message.side_effect = fake_create_msg

    # Mock retrieval returning low similarity (< 0.5)
    mock_retrieval = AsyncMock()
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="Quantum gravity in T Rex?",
        module_filter=None,
        total=1,
        items=[
            AgentSearchResultItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                module_key="scraper",
                source_path="scraper/overview.md",
                file_name="overview.md",
                header_path="Overview",
                content="Irrelevant text",
                similarity=0.15,
            )
        ],
    )

    mock_llm = AsyncMock()

    service = AgentAssistantService(
        db=AsyncMock(),
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        conversation_repo=mock_repo,
    )

    response = await service.ask_in_conversation(
        conversation_id=conv_id,
        user_id=user.user_id,
        question="Quantum gravity in T Rex?",
        similarity_threshold=0.5,
    )

    # LLM must NOT be called
    mock_llm.generate.assert_not_called()
    assert response.assistant_message.content == "I couldn't find enough information in the T Rex documentation to answer that."
    assert response.assistant_message.sources == []
    assert response.assistant_message.generation is None


@pytest.mark.asyncio
async def test_ask_in_conversation_tpi_failure_leaves_user_msg_without_assistant_msg():
    user = create_test_user()
    conv_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_conv = AgentConversation(
        id=conv_id,
        user_id=user.user_id,
        title="Existing Conv",
        created_at=now,
        updated_at=now,
    )

    created_messages = []
    mock_repo = AsyncMock()
    mock_repo.get_conversation.return_value = mock_conv
    mock_repo.get_recent_messages.return_value = []
    mock_repo.touch_updated_at.return_value = None

    def fake_create_msg(conversation_id, role, content, sources=None, generation=None):
        msg = AgentMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            generation=generation,
            created_at=now,
        )
        created_messages.append(msg)
        return msg

    mock_repo.create_message.side_effect = fake_create_msg

    mock_retrieval = AsyncMock()
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="How does scraper work?",
        module_filter=None,
        total=1,
        items=[
            AgentSearchResultItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                module_key="scraper",
                source_path="scraper/overview.md",
                file_name="overview.md",
                header_path="Overview",
                content="Scraper text",
                similarity=0.9,
            )
        ],
    )

    # TPI LLM raises error
    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = TPILlmError("Provider rate limit", retryable=True, code="LLM_RATE_LIMIT")

    service = AgentAssistantService(
        db=AsyncMock(),
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        conversation_repo=mock_repo,
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.ask_in_conversation(
            conversation_id=conv_id,
            user_id=user.user_id,
            question="How does scraper work?",
        )

    assert exc_info.value.status_code == 503
    # User message was persisted
    assert len(created_messages) == 1
    assert created_messages[0].role == "user"
    # Assistant message was NOT created/corrupted
    assert all(m.role != "assistant" for m in created_messages)


@pytest.mark.asyncio
async def test_ask_in_conversation_history_bounding():
    user = create_test_user()
    conv_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_conv = AgentConversation(
        id=conv_id,
        user_id=user.user_id,
        title="Existing",
        created_at=now,
        updated_at=now,
    )

    # 15 previous messages
    previous_messages = [
        AgentMessage(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message turn number {i} " + ("x" * 200),
            sources=[],
            generation=None,
            created_at=now,
        )
        for i in range(15)
    ]

    mock_repo = AsyncMock()
    mock_repo.get_conversation.return_value = mock_conv
    # repo respects limit=10
    mock_repo.get_recent_messages.return_value = previous_messages[-10:]
    mock_repo.touch_updated_at.return_value = None
    mock_repo.create_message.return_value = AgentMessage(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="user",
        content="Current question",
        sources=[],
        generation=None,
        created_at=now,
    )

    mock_retrieval = AsyncMock()
    mock_retrieval.search.return_value = AgentSearchResponse(
        query="Current question",
        module_filter=None,
        total=1,
        items=[
            AgentSearchResultItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                module_key="scraper",
                source_path="scraper/overview.md",
                file_name="overview.md",
                header_path="Overview",
                content="Valid content",
                similarity=0.8,
            )
        ],
    )

    captured_prompts = []
    mock_llm = AsyncMock()
    async def fake_generate(**kwargs):
        captured_prompts.append(kwargs)
        return LLMGenerationResult(
            text="Grounded answer",
            provider="groq",
            model="qwen/qwen3.8-27b",
            input_tokens=100,
            output_tokens=20,
        )
    mock_llm.generate.side_effect = fake_generate

    service = AgentAssistantService(
        db=AsyncMock(),
        retrieval_service=mock_retrieval,
        tpi_llm_client=mock_llm,
        conversation_repo=mock_repo,
    )

    await service.ask_in_conversation(
        conversation_id=conv_id,
        user_id=user.user_id,
        question="Current question",
    )

    assert len(captured_prompts) == 1
    user_prompt = captured_prompts[0]["user_prompt"]
    # Check that history is bounded within max chars
    assert len(user_prompt) < 8000 + 6000 + 500
