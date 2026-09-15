from fastapi import FastAPI

from app.api.email_delivery import router as email_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="T Rex TPI", version="0.1.0")
app.include_router(email_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "tpi",
        "adapters": {"smtp": "configured"},
    }
