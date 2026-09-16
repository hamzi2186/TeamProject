from fastapi import APIRouter
from app.schemas.common import APIResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> APIResponse[dict]:
    return APIResponse.ok({"status": "healthy", "engine": "idea-engine"})
