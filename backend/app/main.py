from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connectivity
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        import logging
        logging.getLogger("calling-engine").warning("DB not reachable on startup: %s", exc)
    yield
    # Shutdown: dispose connection pool
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="T Rex — Calling Engine",
        version="0.1.0",
        description="Outbound/inbound call management for the T Rex platform.",
        lifespan=lifespan,
    )

    # CORS — root frontend and engine frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "calling-engine", "environment": settings.app_env}

    @app.get("/health/db", tags=["system"])
    async def health_db() -> dict[str, str]:
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return {"status": "ok", "db": "connected"}
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=f"DB unavailable: {exc}")

    return app


app = create_app()
