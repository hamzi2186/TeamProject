import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.config import Settings, get_settings
from app.models.agent import AgentMessage
from app.repositories.conversations import AgentConversationRepository
from app.schemas.agent import (
    AgentSearchResultItem,
    AssistantAskResponse,
    AssistantGenerationInfo,
    AssistantSourceItem,
)
from app.schemas.conversations import ConversationAskResponse, MessageResponse
from app.services.retrieval import AgentRetrievalService
from app.services.tpi_client import TPILlmClient, TPILlmError, create_tpi_llm_client

FALLBACK_ANSWER = "I couldn't find enough information in the T Rex documentation to answer that."

SYSTEM_PROMPT = """You are the T Rex platform documentation assistant.
Your task is to answer questions about T Rex modules, workflows, usage,
and platform behavior strictly using the provided documentation sources.

Guidelines:
- Answer using only the provided documentation context.
- Do not invent or assume undocumented platform features or behavior.
- If the documentation context does not contain enough information to answer the question,
  clearly state that you do not have enough information.
- Never expose internal credentials, service tokens, API keys, or provider secrets.
- Do not claim access to customer leads, client websites, or Client Knowledge Base data.
- Maintain module boundaries and provide concise, accurate, and helpful responses
  referencing relevant modules or documentation where appropriate.
"""


class AgentAssistantService:
    def __init__(
        self,
        db: AsyncSession,
        retrieval_service: AgentRetrievalService | None = None,
        tpi_llm_client: TPILlmClient | None = None,
        conversation_repo: AgentConversationRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.retrieval = retrieval_service or AgentRetrievalService(db=db, settings=self.settings)
        self.tpi_llm = tpi_llm_client or create_tpi_llm_client()
        self.repo = conversation_repo or AgentConversationRepository(db=db)

    async def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        module_filter: str | None = None,
        similarity_threshold: float | None = None,
    ) -> AssistantAskResponse:
        """Stateless Phase 2 question answering endpoint."""
        clean_question = question.strip()
        if not clean_question:
            return AssistantAskResponse(answer=FALLBACK_ANSWER, sources=[], generation=None)

        k = top_k or self.settings.agent_assistant_top_k
        min_sim = (
            similarity_threshold
            if similarity_threshold is not None
            else self.settings.agent_assistant_min_similarity
        )

        # 1. Semantic Retrieval over Agent Documentation KB
        search_result = await self.retrieval.search(
            query=clean_question,
            top_k=k,
            module_filter=module_filter,
            similarity_threshold=min_sim,
        )

        if not search_result.items:
            return AssistantAskResponse(answer=FALLBACK_ANSWER, sources=[], generation=None)

        # 2. Verify Groundedness Threshold
        eligible_items = [item for item in search_result.items if item.similarity >= min_sim]
        if not eligible_items:
            return AssistantAskResponse(answer=FALLBACK_ANSWER, sources=[], generation=None)

        # 3. Construct Bounded RAG Context
        context_text, included_items = self._build_bounded_context(
            eligible_items, max_chars=self.settings.agent_assistant_context_max_chars
        )

        if not context_text.strip():
            return AssistantAskResponse(answer=FALLBACK_ANSWER, sources=[], generation=None)

        # 4. Assemble Prompts
        user_prompt = (
            f"Documentation Context:\n{context_text}\n\n"
            f"Question:\n{clean_question}\n\n"
            "Answer:"
        )

        # 5. Call TPI Generic LLM Endpoint
        generation_res = await self.tpi_llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=800,
        )

        # 6. Build Source Attribution
        sources = [
            AssistantSourceItem(
                module_key=item.module_key,
                source_path=item.source_path,
                header_path=item.header_path,
                similarity=item.similarity,
            )
            for item in included_items
        ]

        generation_info = AssistantGenerationInfo(
            provider=generation_res.provider,
            model=generation_res.model,
            input_tokens=generation_res.input_tokens,
            output_tokens=generation_res.output_tokens,
        )

        return AssistantAskResponse(
            answer=generation_res.text,
            sources=sources,
            generation=generation_info,
        )

    async def ask_in_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        question: str,
        *,
        top_k: int | None = None,
        module_filter: str | None = None,
        similarity_threshold: float | None = None,
    ) -> ConversationAskResponse:
        """Multi-turn persistent conversational RAG assistant."""
        clean_question = question.strip()
        if not clean_question:
            raise HTTPException(status_code=422, detail="Question cannot be empty")

        conversation = await self.repo.get_conversation(conversation_id, user_id, load_messages=False)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # 1. Fetch recent history BEFORE persisting current user message (prevents duplicate)
        history_messages = await self.repo.get_recent_messages(
            conversation_id, limit=self.settings.agent_assistant_history_max_messages
        )

        # 2. Derive initial conversation title if unset
        if not conversation.title:
            derived_title = clean_question[:60].strip()
            await self.repo.update_title(conversation_id, user_id, derived_title)

        # 3. Persist user message
        user_msg = await self.repo.create_message(
            conversation_id=conversation_id,
            role="user",
            content=clean_question,
        )
        await self.repo.touch_updated_at(conversation_id)

        # 4. Semantic Retrieval across Agent KB
        k = top_k or self.settings.agent_assistant_top_k
        min_sim = (
            similarity_threshold
            if similarity_threshold is not None
            else self.settings.agent_assistant_min_similarity
        )
        search_result = await self.retrieval.search(
            query=clean_question,
            top_k=k,
            module_filter=module_filter,
            similarity_threshold=min_sim,
        )

        eligible_items = (
            [item for item in search_result.items if item.similarity >= min_sim]
            if search_result.items
            else []
        )

        # 5. Deterministic fallback if insufficient context
        if not eligible_items:
            assistant_msg = await self.repo.create_message(
                conversation_id=conversation_id,
                role="assistant",
                content=FALLBACK_ANSWER,
                sources=[],
                generation=None,
            )
            await self.repo.touch_updated_at(conversation_id)
            return ConversationAskResponse(
                conversation_id=conversation_id,
                user_message=self._to_message_response(user_msg),
                assistant_message=self._to_message_response(assistant_msg),
            )

        # 6. Build bounded context and history
        context_text, included_items = self._build_bounded_context(
            eligible_items, max_chars=self.settings.agent_assistant_context_max_chars
        )
        if not context_text.strip():
            assistant_msg = await self.repo.create_message(
                conversation_id=conversation_id,
                role="assistant",
                content=FALLBACK_ANSWER,
                sources=[],
                generation=None,
            )
            await self.repo.touch_updated_at(conversation_id)
            return ConversationAskResponse(
                conversation_id=conversation_id,
                user_message=self._to_message_response(user_msg),
                assistant_message=self._to_message_response(assistant_msg),
            )

        history_text = self._build_bounded_history(
            history_messages, max_chars=self.settings.agent_assistant_history_max_chars
        )

        # 7. Assemble prompts
        multi_turn_system_prompt = (
            SYSTEM_PROMPT
            + "\nNote on Conversation History:\n"
            "- The conversation history is provided solely for conversational continuity (e.g. resolving pronouns or follow-up references).\n"
            "- The provided Documentation Context remains the sole authoritative factual ground.\n"
            "- Do not treat previous statements in history as factual documentation unless supported by the Documentation Context."
        )

        user_prompt = (
            f"Documentation Context:\n{context_text}\n\n"
            f"Conversation History:\n{history_text}\n\n"
            f"Current Question:\n{clean_question}\n\n"
            "Answer:"
        )

        # 8. Call TPI Generic LLM Endpoint
        try:
            generation_res = await self.tpi_llm.generate(
                system_prompt=multi_turn_system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=800,
            )
        except TPILlmError as exc:
            status_code = 503 if exc.retryable else 502
            raise HTTPException(
                status_code=status_code,
                detail={"code": exc.code, "message": str(exc), "retryable": exc.retryable},
            ) from exc

        # 9. Persist Assistant Response
        sources = [
            AssistantSourceItem(
                module_key=item.module_key,
                source_path=item.source_path,
                header_path=item.header_path,
                similarity=item.similarity,
            )
            for item in included_items
        ]
        generation_info = AssistantGenerationInfo(
            provider=generation_res.provider,
            model=generation_res.model,
            input_tokens=generation_res.input_tokens,
            output_tokens=generation_res.output_tokens,
        )
        assistant_msg = await self.repo.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content=generation_res.text,
            sources=[s.model_dump() for s in sources],
            generation=generation_info.model_dump(),
        )
        await self.repo.touch_updated_at(conversation_id)

        return ConversationAskResponse(
            conversation_id=conversation_id,
            user_message=self._to_message_response(user_msg),
            assistant_message=self._to_message_response(assistant_msg),
        )

    def _to_message_response(self, msg: AgentMessage) -> MessageResponse:
        sources_list = []
        if isinstance(msg.sources, list):
            for s in msg.sources:
                if isinstance(s, dict):
                    sources_list.append(AssistantSourceItem(**s))
        gen_info = None
        if isinstance(msg.generation, dict) and msg.generation:
            gen_info = AssistantGenerationInfo(**msg.generation)

        return MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            sources=sources_list,
            generation=gen_info,
            created_at=msg.created_at,
        )

    def _build_bounded_history(self, messages: list[AgentMessage], max_chars: int) -> str:
        if not messages:
            return "No previous conversation history."
        selected = []
        current_len = 0
        for msg in reversed(messages):
            entry = f"{msg.role.upper()}: {msg.content}"
            if current_len + len(entry) + 1 <= max_chars:
                selected.append(entry)
                current_len += len(entry) + 1
            else:
                break
        selected.reverse()
        return "\n".join(selected) if selected else "No previous conversation history."

    def _build_bounded_context(
        self, items: list[AgentSearchResultItem], max_chars: int
    ) -> tuple[str, list[AgentSearchResultItem]]:
        chunks_text: list[str] = []
        included: list[AgentSearchResultItem] = []
        current_len = 0

        for i, item in enumerate(items, start=1):
            header = item.header_path or "General"
            snippet = (
                f"SOURCE {i}\n"
                f"module: {item.module_key}\n"
                f"path: {item.source_path}\n"
                f"header: {header}\n"
                f"content:\n{item.content}\n"
            )
            snippet_len = len(snippet)

            if current_len + snippet_len <= max_chars:
                chunks_text.append(snippet)
                included.append(item)
                current_len += snippet_len
            else:
                # If first item exceeds max_chars, truncate its content deterministically
                if not included:
                    prefix = (
                        f"SOURCE {i}\n"
                        f"module: {item.module_key}\n"
                        f"path: {item.source_path}\n"
                        f"header: {header}\n"
                        f"content:\n"
                    )
                    remaining = max(0, max_chars - len(prefix) - 5)
                    truncated_content = item.content[:remaining] + "..."
                    snippet = prefix + truncated_content + "\n"
                    chunks_text.append(snippet)
                    included.append(item)
                break

        return "\n".join(chunks_text), included
