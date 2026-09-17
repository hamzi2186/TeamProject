import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentConversation, AgentMessage


class AgentConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_conversation(
        self, user_id: uuid.UUID, title: str | None = None
    ) -> AgentConversation:
        now = datetime.now(UTC)
        conversation = AgentConversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def list_conversations(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[AgentConversation]:
        stmt = (
            select(AgentConversation)
            .where(AgentConversation.user_id == user_id)
            .order_by(AgentConversation.updated_at.desc(), AgentConversation.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, *, load_messages: bool = True
    ) -> AgentConversation | None:
        stmt = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == user_id,
        )
        if load_messages:
            stmt = stmt.options(selectinload(AgentConversation.messages))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_title(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, title: str
    ) -> AgentConversation | None:
        conversation = await self.get_conversation(
            conversation_id, user_id, load_messages=False
        )
        if not conversation:
            return None
        now = datetime.now(UTC)
        conversation.title = title
        conversation.updated_at = now
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def touch_updated_at(self, conversation_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(AgentConversation)
            .where(AgentConversation.id == conversation_id)
            .values(updated_at=now)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def delete_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        stmt = (
            delete(AgentConversation)
            .where(
                AgentConversation.id == conversation_id,
                AgentConversation.user_id == user_id,
            )
            .returning(AgentConversation.id)
        )
        result = await self.db.execute(stmt)
        deleted_id = result.scalar_one_or_none()
        if deleted_id:
            await self.db.commit()
            return True
        return False

    async def create_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        generation: dict | None = None,
    ) -> AgentMessage:
        now = datetime.now(UTC)
        message = AgentMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            generation=generation,
            created_at=now,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_recent_messages(
        self, conversation_id: uuid.UUID, limit: int = 10
    ) -> list[AgentMessage]:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # Return in chronological order (oldest to newest)
        return messages
