from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.conversations import router as conversations_router
from app.api.internal_events import router as internal_events_router
from app.api.websocket import router as websocket_router
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()
allowed_frontend_origins = list(
    dict.fromkeys((settings.frontend_url, settings.platform_frontend_url))
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="T Rex SMS Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(conversations_router)
app.include_router(internal_events_router)
app.include_router(websocket_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "sms-engine"}


@app.get("/health/db")
async def database_health() -> dict:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
