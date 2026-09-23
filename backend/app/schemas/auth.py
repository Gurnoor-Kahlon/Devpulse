from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]
Token = Annotated[SecretStr, Field(min_length=43, max_length=43, strict=True)]


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: Annotated[EmailStr, Field(max_length=254)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RegisterRequest(EmailRequest):
    password: Password


class LoginRequest(EmailRequest):
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    token: Token


class ResetRequest(TokenRequest):
    password: Password


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    email_verified_at: datetime | None


class MessageResponse(BaseModel):
    message: str


class CsrfResponse(BaseModel):
    csrf_token: str
