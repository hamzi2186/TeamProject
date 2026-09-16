import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import get_settings


@dataclass(frozen=True)
class MockSendResult:
    sid: str
    status: str
    from_number: str


@dataclass(frozen=True)
class CapturedMessage:
    provider_message_id: str
    user_id: uuid.UUID
    from_number: str
    to_number: str
    body: str
    status: str
    created_at: datetime


messages: deque[CapturedMessage] = deque(maxlen=500)


async def send_message(
    user_id: uuid.UUID, to_number: str, body: str
) -> MockSendResult:
    sender = get_settings().mock_sms_from_number
    sid = f"SMmock{uuid.uuid4().hex}"
    messages.appendleft(
        CapturedMessage(
            provider_message_id=sid,
            user_id=user_id,
            from_number=sender,
            to_number=to_number,
            body=body,
            status="DELIVERED",
            created_at=datetime.now(UTC),
        )
    )
    return MockSendResult(sid=sid, status="DELIVERED", from_number=sender)
