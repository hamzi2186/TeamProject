import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.repositories.conversations import AgentConversationRepository
from app.schemas.conversations import (
    ConversationAskResponse,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationMessageCreateRequest,
    ConversationSummaryResponse,
    ConversationUpdateRequest,
    MessageResponse,
)
from app.services.assistant import AgentAssistantService

router = APIRouter(prefix="/api/v1/agent/conversations", tags=["agent-conversations"])


@router.post("", response_model=ConversationSummaryResponse, status_code=201)
async def create_conversation(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ConversationCreateRequest | None = None,
) -> ConversationSummaryResponse:
    repo = AgentConversationRepository(db)
    title = payload.title if payload else None
    conversation = await repo.create_conversation(user_id=user.user_id, title=title)
    return ConversationSummaryResponse.model_validate(conversation)


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ConversationSummaryResponse]:
    repo = AgentConversationRepository(db)
    conversations = await repo.list_conversations(user.user_id, limit=limit, offset=offset)
    return [ConversationSummaryResponse.model_validate(c) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationDetailResponse:
    repo = AgentConversationRepository(db)
    conversation = await repo.get_conversation(conversation_id, user.user_id, load_messages=True)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    assistant_service = AgentAssistantService(db=db, conversation_repo=repo)
    messages = [assistant_service._to_message_response(m) for m in conversation.messages]
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
    )


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
async def rename_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationSummaryResponse:
    repo = AgentConversationRepository(db)
    conversation = await repo.update_title(conversation_id, user.user_id, payload.title.strip())
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationSummaryResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = AgentConversationRepository(db)
    deleted = await repo.delete_conversation(conversation_id, user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post("/{conversation_id}/messages", response_model=ConversationAskResponse)
async def post_message_in_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationMessageCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationAskResponse:
    assistant_service = AgentAssistantService(db=db)
    return await assistant_service.ask_in_conversation(
        conversation_id=conversation_id,
        user_id=user.user_id,
        question=payload.content,
        top_k=payload.top_k,
        module_filter=payload.module_filter,
        similarity_threshold=payload.similarity_threshold,
    )
