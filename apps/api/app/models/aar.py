"""Metric snapshots and generated After Action Review reports."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, uuid_pk


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (Index("ix_metric_snapshots_room_sim", "room_id", "sim_time"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE")
    )
    sim_time: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = created_at_col()
    communication_health: Mapped[float] = mapped_column(Float)
    information_completeness: Mapped[float] = mapped_column(Float)
    information_reliability: Mapped[float] = mapped_column(Float)
    uncertainty_index: Mapped[float] = mapped_column(Float)
    decision_quality: Mapped[float | None] = mapped_column(Float)
    coordination_score: Mapped[float | None] = mapped_column(Float)


class AARReport(Base):
    __tablename__ = "aar_reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), unique=True
    )
    generated_at: Mapped[datetime] = created_at_col()
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(Text)
    team_score: Mapped[float] = mapped_column(Float)
    report_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Narrative text only - AI output never touches historical simulation records.
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    narrative_source: Mapped[str] = mapped_column(String(16), default="TEMPLATE")
