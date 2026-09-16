from fastapi import APIRouter

from app.api.v1.routes.calling import router as calling_router
from app.api.v1.routes.calling import webhook_router

api_router = APIRouter()
api_router.include_router(calling_router, prefix="/calling", tags=["calling"])
api_router.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])
