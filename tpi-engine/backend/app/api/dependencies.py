import secrets
from typing import Annotated

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_service_token(
    x_tpi_service_token: Annotated[str, Header()],
) -> None:
    expected = get_settings().tpi_internal_service_token
    if not secrets.compare_digest(x_tpi_service_token, expected):
        raise HTTPException(401, "Invalid internal service credentials")
