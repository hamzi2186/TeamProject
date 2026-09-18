import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import logger, setup_logging
from app.db.session import Base, engine
from app.models.idea_reports import IdeaLeadReportItem, IdeaReportRun
from app.schemas.common import APIResponse

settings = get_settings()
setup_logging(settings.app_env)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing T Rex Idea Engine backend...")
    # Ensure reports directory exists
    os.makedirs(settings.reports_storage_dir, exist_ok=True)

    # Initialize only Idea Engine's own tables. The shared platform tables
    # (leads, calls, sms_messages, emails, campaigns, conversations, ...) are
    # owned and migrated by the root backend; we must never materialize them.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    bind=sync_conn,
                    tables=[IdeaReportRun.__table__, IdeaLeadReportItem.__table__],
                )
            )
            logger.info("Idea Engine tables initialized successfully.")
    except Exception as exc:
        logger.warning(f"Could not initialize database tables: {exc}")

    yield

    logger.info("Shutting down T Rex Idea Engine backend...")
    await engine.dispose()


app = FastAPI(
    title="T Rex Idea Engine",
    description="Lead Intelligence & Autonomous Multi-Channel Daily DOCX Reporting Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
origins = [o.strip() for o in settings.frontend_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content=APIResponse.fail(
            code="INTERNAL_SERVER_ERROR",
            message=str(exc) if settings.app_env != "production" else "An unexpected internal error occurred.",
        ).model_dump(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8006, reload=True)
