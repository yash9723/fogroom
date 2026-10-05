import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, created_at_col, enum_check, uuid_pk
from app.models.enums import UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (enum_check("role", UserRole),)

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.TRAINEE.value)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshToken(Base):
    """Hashed refresh token. Tokens rotate on every use; reuse of a rotated
    token revokes the whole family (theft detection)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
