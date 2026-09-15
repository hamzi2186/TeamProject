from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class EmailDeliveryRequest(BaseModel):
    to: EmailStr
    template: Literal["verify_email", "reset_password", "smtp_smoke"]
    variables: dict[str, str] = Field(default_factory=dict)


class EmailDeliveryResponse(BaseModel):
    accepted: bool
    transport: str = "smtp"
