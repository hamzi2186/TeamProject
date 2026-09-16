from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.hubspot import router as hubspot_router
from app.api.leads import router as leads_router
from app.api.v1.routes.mailer import router as mailer_router
from app.core.config import get_settings
from app.core.keys import ensure_jwt_keys
from app.core.security import public_jwk
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_jwt_keys()
    yield
    await engine.dispose()


app = FastAPI(title="T Rex Platform API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(hubspot_router)
app.include_router(leads_router)
app.include_router(mailer_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "root-backend"}


@app.get("/health/db")
async def database_health() -> dict:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/.well-known/jwks.json")
async def jwks() -> dict:
    return {"keys": [public_jwk()]}
