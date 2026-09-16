import asyncio
import json
import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy import select

from app.auth.dependencies import jwk_client
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.sms import SmsConversation

router = APIRouter(tags=["sms-websocket"])


@router.websocket("/ws/sms/conversations/{conversation_id}")
async def conversation_events(websocket: WebSocket, conversation_id: uuid.UUID) -> None:
    user_id = _websocket_user(websocket)
    if user_id is None:
        await websocket.close(code=4401, reason="Authentication required")
        return
    async with SessionLocal() as db:
        owned = await db.scalar(
            select(SmsConversation.id).where(
                SmsConversation.id == conversation_id,
                SmsConversation.user_id == user_id,
            )
        )
    if owned is None:
        await websocket.close(code=4404, reason="Conversation not found")
        return
    await websocket.accept()
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"sms:conversation:{conversation_id}")
    try:
        await websocket.send_json({"type": "connected", "payload": {}})
        while True:
            event = await pubsub.get_message(ignore_subscribe_messages=True, timeout=20)
            if event:
                await websocket.send_json(json.loads(event["data"]))
            else:
                await websocket.send_json({"type": "heartbeat", "payload": {}})
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"sms:conversation:{conversation_id}")
        await pubsub.aclose()
        await redis.aclose()


def _websocket_user(websocket: WebSocket) -> uuid.UUID | None:
    settings = get_settings()
    token = websocket.query_params.get("access_token")
    if token:
        try:
            signing_key = jwk_client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.auth_audience,
                issuer=settings.auth_issuer,
            )
            return uuid.UUID(claims["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            return None
    demo_user_id = websocket.query_params.get("demo_user_id")
    if settings.app_env != "production" and settings.allow_demo_identity and demo_user_id:
        try:
            return uuid.UUID(demo_user_id)
        except ValueError:
            return None
    return None
