from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.routes.calling import router as calling_router
from app.api.v1.routes.calling import webhook_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        if settings.database_url.startswith("sqlite"):
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        import logging
        logging.getLogger("calling-engine").warning("DB connection check on startup: %s", exc)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="T Rex — Calling Engine (Standalone)",
        version="0.1.0",
        description="Autonomous outbound and inbound voice call agent powered by Vapi and Telnyx.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_url,
            "http://localhost:5173",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Calling Engine APIs
    app.include_router(calling_router, prefix="/api/v1/calling", tags=["calling"])
    app.include_router(webhook_router, prefix="/api/v1/webhooks", tags=["webhooks"])

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "calling-engine",
            "mode": "standalone",
            "environment": settings.app_env,
        }

    @app.get("/health/db", tags=["system"])
    async def health_db() -> dict[str, str]:
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return {"status": "ok", "db": "connected"}
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    return app


app = create_app()
