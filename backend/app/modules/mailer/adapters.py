from __future__ import annotations

import asyncio
from uuid import UUID

from app.modules.mailer.contracts import KBPassage
from app.modules.mailer.exceptions import MailerProviderError
from app.services.scraper_client import ScraperClient, ScraperClientError
from app.tpi.llm_client import TPILLMClient, TPILLMError


REPLY_TASK = "mailer.process_inbound_email"
MAILER_QUEUE = "mailer.email"


class CeleryReplyDispatcher:
    """Queues a stored reply for a worker.

    The task is sent by name, so importing this never loads the task code or needs a worker.
    """

    async def enqueue_reply(self, *, conversation_id: UUID, inbound_email_id: UUID) -> None:
        from app.workers.celery_app import celery_app

        # send_task publishes to the broker synchronously, so keep it off the event loop.
        await asyncio.to_thread(
            celery_app.send_task,
            REPLY_TASK,
            kwargs={
                "conversation_id": str(conversation_id),
                "inbound_email_id": str(inbound_email_id),
            },
            queue=MAILER_QUEUE,
        )


class TPILLMAdapter:
    """Lets the service use the TPI LLM client while only ever seeing MailerProviderError."""

    def __init__(self, client: TPILLMClient) -> None:
        self._client = client

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 900,
    ) -> str:
        try:
            return await self._client.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except TPILLMError as exc:
            raise MailerProviderError(str(exc), retryable=exc.retryable) from exc


class ScraperKnowledgeBase:
    """Reads a lead's Client KB through the scraper's public retrieval contract."""

    _USABLE = {"READY", "PARTIAL"}

    def __init__(self, scraper: ScraperClient, *, role: str = "customer") -> None:
        self._scraper = scraper
        self._role = role

    async def search(
        self, *, user_id: UUID, website_id: UUID | None, query: str, top_k: int
    ) -> list[KBPassage]:
        """Return relevant passages, or none when the lead has no usable knowledge base.

        A lead without a website, or whose site is still being crawled, is not an error: the
        email is written without company claims. An unreachable scraper is an error, so that a
        worker retries instead of sending an ungrounded email by accident.
        """
        if website_id is None or not query.strip():
            return []
        try:
            status = await self._scraper.get_website_status(user_id, self._role, website_id)
        except ScraperClientError as exc:
            raise MailerProviderError(str(exc), retryable=exc.status_code >= 500) from exc
        website = (status or {}).get("website") or {}
        processing = (status or {}).get("processing") or {}
        kb_id = website.get("knowledge_base_id")
        if not kb_id or processing.get("knowledge_base_status") not in self._USABLE:
            return []
        try:
            data = await self._scraper.search_knowledge_base(
                user_id, self._role, UUID(str(kb_id)), query, top_k
            )
        except ScraperClientError as exc:
            if exc.status_code == 409:  # the scraper says the knowledge base is not ready
                return []
            raise MailerProviderError(str(exc), retryable=exc.status_code >= 500) from exc
        return [
            KBPassage(
                content=item["content"],
                source_url=item.get("source_url", ""),
                title=item.get("page_title"),
                similarity=float(item.get("similarity", 0.0)),
            )
            for item in data.get("results", [])
            if item.get("content")
        ]
