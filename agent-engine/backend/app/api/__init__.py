from app.api.admin import router as admin_router
from app.api.assistant import router as assistant_router
from app.api.retrieval import router as retrieval_router

__all__ = ["admin_router", "assistant_router", "retrieval_router"]
