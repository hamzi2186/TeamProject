import uuid
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIErrorDetails(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: APIErrorDetails | None = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def ok(cls, data: T, request_id: str | None = None) -> "APIResponse[T]":
        return cls(
            success=True,
            data=data,
            error=None,
            request_id=request_id or str(uuid.uuid4()),
        )

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> "APIResponse[None]":
        return cls(
            success=False,
            data=None,
            error=APIErrorDetails(
                code=code,
                message=message,
                details=details or {},
            ),
            request_id=request_id or str(uuid.uuid4()),
        )
