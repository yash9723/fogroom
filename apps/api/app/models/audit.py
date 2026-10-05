"""Append-only audit / simulation event stream (replay source of truth)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Identity, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, enum_check
from app.models.enums import ActorType, EventVisibility


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("room_id", "seq", name="uq_audit_events_room_seq"),
        Index("ix_audit_events_room_type", "room_id", "event_type"),
        enum_check("visibility", EventVisibility),
        enum_check("actor_type", ActorType),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    seq: Mapped[int | None] = mapped_column(BigInteger)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(String(16), default=ActorType.SYSTEM.value)
    event_type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sim_time: Mapped[float | None] = mapped_column(Float)
    visibility: Mapped[str] = mapped_column(String(16), default=EventVisibility.INSTRUCTOR.value)
    target_participant_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    timestamp: Mapped[datetime] = created_at_col()
