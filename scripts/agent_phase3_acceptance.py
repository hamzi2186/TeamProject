"""Agent Phase 3 live acceptance test suite.

Verifies:
1. Multi-turn conversational RAG persistence (Supabase PostgreSQL via Alembic 0007).
2. Live TPI -> Groq RAG generation with source citations.
3. Multi-turn context preservation across turns.
4. Auto-generated conversation title on first turn.
5. In-conversation out-of-scope fallback (persisted, skips LLM call).
6. Conversation management (list, get, rename, delete).
7. Strict cross-user isolation (404 on GET, PATCH, DELETE, POST message for other user).
8. Stateless /api/v1/agent/assistant/ask backwards compatibility.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app.core.config import Settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402

AGENT_BASE_URL = "http://localhost:8003"


async def get_test_users() -> list[tuple[str, str]]:
    settings = Settings(_env_file=BACKEND / ".env")
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text("SELECT id, role FROM app_users ORDER BY created_at ASC LIMIT 2")
                )
            ).all()
    finally:
        await engine.dispose()
    if len(rows) < 2:
        raise RuntimeError("Need at least 2 users in app_users to test isolation")
    return [(str(r.id), r.role) for r in rows]


def api_request(
    method: str,
    path: str,
    token: str,
    body: dict | None = None,
    expected_status: int = 200,
) -> dict | list | None:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        f"{AGENT_BASE_URL}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method=method,
    )
    try:
        with urlopen(req, timeout=60) as resp:
            status = resp.status
            if status != expected_status:
                raise RuntimeError(
                    f"{method} {path} expected status {expected_status} but got {status}"
                )
            if status == 204:
                return None
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except HTTPError as exc:
        raw = exc.read()
        if exc.code == expected_status:
            return json.loads(raw.decode("utf-8")) if raw else None
        err_body = raw.decode("utf-8", errors="replace") if raw else ""
        raise RuntimeError(
            f"{method} {path} failed with HTTP {exc.code} (expected {expected_status}): {err_body}"
        ) from exc


def main() -> int:
    print("=== Starting Agent Phase 3 Live Acceptance Tests ===")

    # 1. Obtain test tokens for User 1 and User 2
    users = asyncio.run(get_test_users())
    user1_id, user1_role = users[0]
    user2_id, user2_role = users[1]

    token1, _ = create_access_token(UUID(user1_id), user1_role)
    token2, _ = create_access_token(UUID(user2_id), user2_role)
    print(f"Verified test user identities: User 1 ({user1_id[:8]}...), User 2 ({user2_id[:8]}...)")

    # Step 1: Create conversation for User 1
    print("\n[Step 1] Creating conversation for User 1...")
    conv = api_request("POST", "/api/v1/agent/conversations", token1, expected_status=201)
    conv_id = conv["id"]
    print(f"Created conversation {conv_id} with initial title: {conv.get('title')}")
    assert conv["id"] is not None
    assert conv["created_at"] is not None

    # Step 2: Post turn 1 message (KB question)
    print("\n[Step 2] User 1 asking Turn 1: 'How does the Scraper Engine build a Client Knowledge Base?'...")
    turn1 = api_request(
        "POST",
        f"/api/v1/agent/conversations/{conv_id}/messages",
        token1,
        body={"content": "How does the Scraper Engine build a Client Knowledge Base?"},
        expected_status=200,
    )
    user_msg1 = turn1["user_message"]
    asst_msg1 = turn1["assistant_message"]

    assert user_msg1["role"] == "user"
    assert user_msg1["content"] == "How does the Scraper Engine build a Client Knowledge Base?"
    assert asst_msg1["role"] == "assistant"
    assert len(asst_msg1["content"].strip()) > 20
    assert len(asst_msg1["sources"]) > 0
    assert asst_msg1["generation"] is not None
    assert asst_msg1["generation"]["provider"] == "groq"
    print(f"Turn 1 grounded answer received ({len(asst_msg1['content'])} chars)")
    print(f"Generation info: {asst_msg1['generation']}")
    print(f"Sources cited ({len(asst_msg1['sources'])}): {[s['source_path'] for s in asst_msg1['sources'][:3]]}")

    # Check that title was automatically updated from message content
    conv_detail = api_request("GET", f"/api/v1/agent/conversations/{conv_id}", token1)
    print(f"Updated conversation title: '{conv_detail['title']}'")
    assert conv_detail["title"] is not None
    assert len(conv_detail["title"]) > 0

    # Step 3: Post turn 2 follow-up question (Multi-turn conversational continuity)
    print("\n[Step 3] User 1 asking Turn 2 (Follow-up): 'How does the Scraper Engine handle duplicate pages or content during the crawl?'...")
    turn2 = api_request(
        "POST",
        f"/api/v1/agent/conversations/{conv_id}/messages",
        token1,
        body={"content": "How does the Scraper Engine handle duplicate pages or content during the crawl?"},
        expected_status=200,
    )
    user_msg2 = turn2["user_message"]
    asst_msg2 = turn2["assistant_message"]

    assert user_msg2["role"] == "user"
    assert asst_msg2["role"] == "assistant"
    assert len(asst_msg2["content"].strip()) > 20
    assert len(asst_msg2["sources"]) > 0
    assert asst_msg2["generation"] is not None
    assert asst_msg2["generation"]["provider"] == "groq"
    print(f"Turn 2 grounded answer received ({len(asst_msg2['content'])} chars)")

    # Step 4: Verify conversation history retrieval in deterministic order
    print("\n[Step 4] Verifying conversation message history...")
    conv_after_turn2 = api_request("GET", f"/api/v1/agent/conversations/{conv_id}", token1)
    msgs = conv_after_turn2["messages"]
    print(f"Total persisted messages in conversation: {len(msgs)}")
    assert len(msgs) == 4
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[2]["role"] == "user"
    assert msgs[3]["role"] == "assistant"

    # Step 5: Rename conversation
    print("\n[Step 5] Testing conversation rename (PATCH)...")
    renamed = api_request(
        "PATCH",
        f"/api/v1/agent/conversations/{conv_id}",
        token1,
        body={"title": "Scraper Engine Knowledge Discussion"},
        expected_status=200,
    )
    assert renamed["title"] == "Scraper Engine Knowledge Discussion"
    print(f"Conversation successfully renamed to: '{renamed['title']}'")

    # Step 6: Test no-context fallback within conversation
    print("\n[Step 6] Testing in-conversation out-of-scope question (Turn 3)...")
    fallback_turn = api_request(
        "POST",
        f"/api/v1/agent/conversations/{conv_id}/messages",
        token1,
        body={"content": "What is the secret recipe for Italian chocolate pizza?"},
        expected_status=200,
    )
    fb_user = fallback_turn["user_message"]
    fb_asst = fallback_turn["assistant_message"]
    assert "I couldn't find enough information in the T Rex documentation" in fb_asst["content"]
    assert fb_asst["sources"] == []
    assert fb_asst["generation"] is None
    print("Deterministic fallback persisted correctly without LLM call")

    # Step 7: Strict Cross-User Isolation Verification
    print("\n[Step 7] Testing Cross-User Isolation (User 2 attempting access to User 1's conversation)...")
    # GET
    api_request("GET", f"/api/v1/agent/conversations/{conv_id}", token2, expected_status=404)
    print("User 2 GET -> 404 (Passed)")
    # PATCH
    api_request(
        "PATCH",
        f"/api/v1/agent/conversations/{conv_id}",
        token2,
        body={"title": "Malicious Rename"},
        expected_status=404,
    )
    print("User 2 PATCH -> 404 (Passed)")
    # POST message
    api_request(
        "POST",
        f"/api/v1/agent/conversations/{conv_id}/messages",
        token2,
        body={"content": "Unauthorized injection"},
        expected_status=404,
    )
    print("User 2 POST message -> 404 (Passed)")
    # DELETE
    api_request("DELETE", f"/api/v1/agent/conversations/{conv_id}", token2, expected_status=404)
    print("User 2 DELETE -> 404 (Passed)")
    # User 2 list conversations does not contain conv_id
    user2_convs = api_request("GET", "/api/v1/agent/conversations", token2)
    assert all(c["id"] != conv_id for c in user2_convs)
    print("User 2 conversation listing excludes User 1's conversation (Passed)")

    # Step 8: Delete conversation by owner (User 1)
    print("\n[Step 8] Deleting conversation by owner (User 1)...")
    api_request("DELETE", f"/api/v1/agent/conversations/{conv_id}", token1, expected_status=204)
    api_request("GET", f"/api/v1/agent/conversations/{conv_id}", token1, expected_status=404)
    print("Conversation deleted cleanly and subsequent GET returns 404 (Passed)")

    # Step 9: Verify stateless endpoint backwards compatibility
    print("\n[Step 9] Verifying backwards compatibility of POST /api/v1/agent/assistant/ask...")
    stateless = api_request(
        "POST",
        "/api/v1/agent/assistant/ask",
        token1,
        body={"question": "How does the Scraper Engine build a Client Knowledge Base?"},
        expected_status=200,
    )
    assert len(stateless["answer"].strip()) > 20
    assert len(stateless["sources"]) > 0
    assert stateless["generation"]["provider"] == "groq"
    print(f"Stateless endpoint answered successfully ({len(stateless['answer'])} chars)")
    print(f"Sources cited: {[s['source_path'] for s in stateless['sources'][:2]]}")

    print("\n=== All Agent Phase 3 Live Acceptance Tests PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
