from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.schemas.agent import (
    AgentSearchResultItem,
    AssistantAskResponse,
    AssistantGenerationInfo,
    AssistantSourceItem,
)
from app.services.retrieval import AgentRetrievalService
from app.services.tpi_client import TPILlmClient, create_tpi_llm_client

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
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.retrieval = retrieval_service or AgentRetrievalService(db=db, settings=self.settings)
        self.tpi_llm = tpi_llm_client or create_tpi_llm_client()

    async def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        module_filter: str | None = None,
        similarity_threshold: float | None = None,
    ) -> AssistantAskResponse:
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
