from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.dependencies import require_service_token
from app.contracts.llm import LLMGenerateRequest, LLMGenerateResponse
from app.providers.llm.errors import LLMError
from app.providers.llm.service import LLMService, get_llm_service

router = APIRouter(
    prefix="/api/v1/internal/llm",
    tags=["internal-llm"],
    dependencies=[Depends(require_service_token)],
)


def normalized_error(error: LLMError) -> HTTPException:
    return HTTPException(
        status_code=error.http_status,
        detail={"code": error.code, "message": str(error), "retryable": error.retryable},
    )


@router.post("/generate", response_model=LLMGenerateResponse)
async def generate_completion(
    payload: LLMGenerateRequest,
    service: Annotated[LLMService, Depends(get_llm_service)],
    x_consumer_engine: Annotated[str | None, Header(alias="X-Consumer-Engine")] = None,
) -> LLMGenerateResponse:
    try:
        return await service.generate(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            consumer=payload.consumer or x_consumer_engine,
        )
    except LLMError as exc:
        raise normalized_error(exc) from exc
