from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class RegisterResponse(BaseModel):
    message: str
    verification_email_sent: bool


class EmailOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(EmailOtpRequest):
    new_password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    role: str
    email_verified_at: datetime | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    user: UserResponse
