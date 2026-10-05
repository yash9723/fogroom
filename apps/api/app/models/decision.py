"""Decisions and the information snapshot captured at the moment of decision."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, uuid_pk


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint(
            "room_id", "participant_id", "decision_point_id", name="uq_decisions_one_per_point"
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="confidence_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    decision_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room_decision_points.id", ondelete="CASCADE")
    )
    scenario_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_events.id", ondelete="SET NULL")
    )
    decision_type: Mapped[str] = mapped_column(String(16))  # OPTION | CUSTOM
    selected_option: Mapped[str | None] = mapped_column(String(60))
    decision_text: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = created_at_col()
    submitted_sim_time: Mapped[float] = mapped_column(Float)
    response_time_ms: Mapped[int] = mapped_column(Integer)


class InformationSnapshot(Base):
    """Frozen digital twin of a participant's information state at a decision."""

    __tablename__ = "information_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.id", ondelete="CASCADE"), unique=True
    )
    snapshot_time: Mapped[float] = mapped_column(Float)  # simulation seconds
    created_at: Mapped[datetime] = created_at_col()
    known_message_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    pending_message_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    unavailable_channel_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    information_completeness: Mapped[float] = mapped_column(Float)
    information_reliability: Mapped[float] = mapped_column(Float)
    communication_health: Mapped[float] = mapped_column(Float)
    contradiction_count: Mapped[int] = mapped_column(Integer, default=0)
    uncertainty_score: Mapped[float] = mapped_column(Float)
    snapshot_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
