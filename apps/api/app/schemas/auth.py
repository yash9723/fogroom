import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def _strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain letters and numbers.")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=256)


class DemoLoginIn(BaseModel):
    persona: Literal["instructor", "alpha", "bravo", "charlie", "admin"]


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
