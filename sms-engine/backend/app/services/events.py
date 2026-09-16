import json
import uuid

from redis.asyncio import Redis

from app.core.config import get_settings


async def publish_conversation_event(
    conversation_id: uuid.UUID, event_type: str, payload: dict
) -> None:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis.publish(
            f"sms:conversation:{conversation_id}",
            json.dumps({"type": event_type, "payload": payload}, default=str),
        )
    finally:
        await redis.aclose()
