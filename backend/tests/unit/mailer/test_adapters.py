import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.modules.mailer.adapters import ScraperKnowledgeBase, TPILLMAdapter
from app.modules.mailer.config import MailerSettings
from app.modules.mailer.exceptions import MailerProviderError
from app.services.scraper_client import ScraperClientError
from app.tpi.llm_client import TPILLMClient, TPILLMError


@pytest.fixture(autouse=True)
def tpi_settings(monkeypatch):
    monkeypatch.setattr(
        "app.tpi.llm_client.get_settings",
        lambda: SimpleNamespace(tpi_api_base_url="https://tpi.example/", tpi_internal_service_token="tok"),
    )


def llm_client(handler) -> TPILLMClient:
    return TPILLMClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def generate(client):
    return await client.generate_text(system_prompt="sys", user_prompt="usr")


# -- the TPI LLM client ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_llm_client_speaks_the_tpi_contract():
    seen = {}

    def handler(request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json={"text": "hello", "provider": "groq", "model": "m", "usage": {}})

    assert await generate(llm_client(handler)) == "hello"
    assert seen["url"] == "https://tpi.example/api/v1/internal/llm/generate"
    assert seen["headers"]["x-tpi-service-token"] == "tok"
    assert seen["headers"]["x-consumer-engine"] == "mailer"
    assert seen["body"] == {"system_prompt": "sys", "user_prompt": "usr", "temperature": 0.3,
                            "max_tokens": 900, "consumer": "mailer"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "retryable"),
    [
        (httpx.Response(503), True),
        (httpx.Response(429), True),
        (httpx.Response(400), False),
        (httpx.Response(401), False),
        (httpx.Response(502, json={"detail": {"code": "x", "message": "m", "retryable": False}}), False),
        (httpx.Response(400, json={"detail": {"code": "x", "message": "m", "retryable": True}}), True),
        (httpx.Response(502, text="<html>gateway</html>"), True),
    ],
)
async def test_llm_errors_say_whether_trying_again_could_help(response, retryable):
    with pytest.raises(TPILLMError) as raised:
        await generate(llm_client(lambda request: response))
    assert raised.value.retryable is retryable


@pytest.mark.asyncio
async def test_an_unreachable_llm_service_is_retryable():
    def handler(request):
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(TPILLMError) as raised:
        await generate(llm_client(handler))
    assert raised.value.retryable is True


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"nope": 1}, {"text": ""}, {"text": "   "}, {"text": 5}, ["x"]])
async def test_a_malformed_llm_response_is_an_error(body):
    with pytest.raises(TPILLMError):
        await generate(llm_client(lambda request: httpx.Response(200, json=body)))


class _BrokenClient:
    def __init__(self, error):
        self.error = error

    async def generate_text(self, **_):
        if self.error:
            raise self.error
        return "fine"


@pytest.mark.asyncio
async def test_the_adapter_only_ever_raises_mailer_errors():
    assert await TPILLMAdapter(_BrokenClient(None)).generate_text(system_prompt="s", user_prompt="u") == "fine"
    with pytest.raises(MailerProviderError) as raised:
        await TPILLMAdapter(_BrokenClient(TPILLMError("boom", retryable=False))).generate_text(
            system_prompt="s", user_prompt="u"
        )
    assert raised.value.retryable is False


# -- the knowledge base adapter ------------------------------------------------------------


class FakeScraper:
    def __init__(self, status=None, results=None, status_error=None, search_error=None):
        self.status, self.results = status, results or []
        self.status_error, self.search_error = status_error, search_error
        self.status_calls, self.search_calls = [], []

    async def get_website_status(self, user_id, role, website_id):
        self.status_calls.append((user_id, role, website_id))
        if self.status_error:
            raise self.status_error
        return self.status

    async def search_knowledge_base(self, user_id, role, kb_id, query, top_k=6):
        self.search_calls.append((user_id, role, kb_id, query, top_k))
        if self.search_error:
            raise self.search_error
        return {"knowledge_base_id": str(kb_id), "query": query, "results": self.results}


def ready(kb_id, status="READY"):
    return {"website": {"knowledge_base_id": str(kb_id)}, "processing": {"knowledge_base_status": status}}


PASSAGE = {"chunk_id": str(uuid4()), "content": "We sell skates.", "source_url": "https://a.example/x",
           "page_title": "Skates", "similarity": 0.83}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["READY", "PARTIAL"])
async def test_a_usable_knowledge_base_is_searched_on_the_leads_behalf(status):
    user, website, kb_id = uuid4(), uuid4(), uuid4()
    scraper = FakeScraper(status=ready(kb_id, status), results=[PASSAGE, {**PASSAGE, "content": ""}])
    passages = await ScraperKnowledgeBase(scraper).search(user_id=user, website_id=website, query="skates", top_k=4)
    assert scraper.status_calls == [(user, "customer", website)]
    assert scraper.search_calls == [(user, "customer", kb_id, "skates", 4)]
    assert [(p.content, p.source_url, p.title, p.similarity) for p in passages] == [
        ("We sell skates.", "https://a.example/x", "Skates", 0.83)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [None, {}, {"website": {}, "processing": {}},
     ready(uuid4(), "CRAWLING"), ready(uuid4(), "FAILED"), ready(uuid4(), "PENDING")],
)
async def test_a_lead_without_a_usable_knowledge_base_gets_no_passages_and_no_error(status):
    scraper = FakeScraper(status=status)
    assert await ScraperKnowledgeBase(scraper).search(user_id=uuid4(), website_id=uuid4(), query="q", top_k=6) == []
    assert scraper.search_calls == []


@pytest.mark.asyncio
async def test_nothing_is_asked_when_there_is_no_website_or_no_question():
    scraper = FakeScraper(status=ready(uuid4()))
    kb = ScraperKnowledgeBase(scraper)
    assert await kb.search(user_id=uuid4(), website_id=None, query="q", top_k=6) == []
    assert await kb.search(user_id=uuid4(), website_id=uuid4(), query="  ", top_k=6) == []
    assert scraper.status_calls == []


@pytest.mark.asyncio
async def test_a_knowledge_base_the_scraper_says_is_not_ready_is_not_an_error():
    scraper = FakeScraper(status=ready(uuid4()), search_error=ScraperClientError("not ready", status_code=409))
    assert await ScraperKnowledgeBase(scraper).search(user_id=uuid4(), website_id=uuid4(), query="q", top_k=6) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("status_code", "retryable"), [(503, True), (502, True), (400, False), (403, False)])
@pytest.mark.parametrize("where", ["status", "search"])
async def test_a_scraper_failure_is_an_error_so_a_worker_retries_instead_of_writing_blind(where, status_code, retryable):
    error = ScraperClientError("scraper failed", status_code=status_code)
    scraper = (FakeScraper(status_error=error) if where == "status"
               else FakeScraper(status=ready(uuid4()), search_error=error))
    with pytest.raises(MailerProviderError) as raised:
        await ScraperKnowledgeBase(scraper).search(user_id=uuid4(), website_id=uuid4(), query="q", top_k=6)
    assert raised.value.retryable is retryable


# -- settings -------------------------------------------------------------------------------


def test_settings_default_to_the_prd_values_and_no_secret():
    settings = MailerSettings(_env_file=None)
    assert settings.max_autonomous_text_turns == 20
    assert settings.mailer_reply_token_secret == "" and settings.mailer_reply_to_domain == ""
    assert (settings.mailer_reply_to_mailbox, settings.mailer_kb_top_k) == ("mailer", 6)


def test_settings_are_read_from_the_documented_environment_variables(monkeypatch):
    monkeypatch.setenv("MAX_AUTONOMOUS_TEXT_TURNS", "5")
    monkeypatch.setenv("MAILER_REPLY_TOKEN_SECRET", "s3cret")
    monkeypatch.setenv("MAILER_REPLY_TO_DOMAIN", "reply.example.com")
    settings = MailerSettings(_env_file=None)
    assert (settings.max_autonomous_text_turns, settings.mailer_reply_token_secret) == (5, "s3cret")
    assert settings.mailer_reply_to_domain == "reply.example.com"


def test_the_turn_limit_cannot_be_disabled_by_setting_it_to_zero(monkeypatch):
    monkeypatch.setenv("MAX_AUTONOMOUS_TEXT_TURNS", "0")
    with pytest.raises(ValidationError):
        MailerSettings(_env_file=None)
