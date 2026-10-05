"""Live exercise state: rooms, participants, channels, decision points."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, created_at_col, enum_check, uuid_pk
from app.models.enums import ChannelStatus, ConnectionStatus, DecisionPointStatus, RoomStatus


class SimulationRoom(Base):
    __tablename__ = "simulation_rooms"
    __table_args__ = (enum_check("status", RoomStatus),)

    id: Mapped[uuid.UUID] = uuid_pk()
    room_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    scenario_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="SET NULL"), index=True
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default=RoomStatus.LOBBY.value, index=True)
    seed: Mapped[int] = mapped_column(BigInteger)
    time_scale: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = created_at_col()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # real_started_at
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_pause_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    # Simulation clock anchor: sim_now = sim_anchor_seconds + (wall - anchor_at) * time_scale
    sim_anchor_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    anchor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_sim_seconds: Mapped[float | None] = mapped_column(Float)

    current_phase_key: Mapped[str | None] = mapped_column(String(40))
    event_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    message_seq: Mapped[int] = mapped_column(Integer, default=100)
    last_metrics_sim_time: Mapped[float] = mapped_column(Float, default=-1.0)
    # Frozen copy of the scenario template at room creation (immutability for replay).
    scenario_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    participants: Mapped[list["Participant"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="Participant.joined_at"
    )
    channels: Mapped[list["CommunicationChannel"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="CommunicationChannel.sort_order",
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_participants_room_user"),
        enum_check("connection_status", ConnectionStatus),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    callsign: Mapped[str] = mapped_column(String(40))
    assigned_role: Mapped[str | None] = mapped_column(String(40))
    team: Mapped[str | None] = mapped_column(String(60))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    connection_status: Mapped[str] = mapped_column(
        String(16), default=ConnectionStatus.DISCONNECTED.value
    )
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room: Mapped[SimulationRoom] = relationship(back_populates="participants")


class CommunicationChannel(TimestampMixin, Base):
    __tablename__ = "communication_channels"
    __table_args__ = (
        UniqueConstraint("room_id", "key", name="uq_communication_channels_room_key"),
        enum_check("status", ChannelStatus),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    channel_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default=ChannelStatus.ONLINE.value)
    reliability: Mapped[float] = mapped_column(Float, default=0.95)
    latency_ms: Mapped[int] = mapped_column(Integer, default=500)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    fallback_channel_key: Mapped[str | None] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    room: Mapped[SimulationRoom] = relationship(back_populates="channels")


class ChannelStateChange(Base):
    """Append-only channel history - lets replay reconstruct channel state at any time."""

    __tablename__ = "channel_state_changes"
    __table_args__ = (Index("ix_channel_state_changes_room_sim", "room_id", "sim_time"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communication_channels.id", ondelete="CASCADE"), index=True
    )
    sim_time: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    reliability: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200), default="")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = created_at_col()


class RoomDecisionPoint(Base):
    """A decision point as it actually opened in a specific room."""

    __tablename__ = "room_decision_points"
    __table_args__ = (
        UniqueConstraint("room_id", "key", name="uq_room_decision_points_room_key"),
        enum_check("status", DecisionPointStatus),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    allow_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    require_rationale: Mapped[bool] = mapped_column(Boolean, default=True)
    target_participant_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    relevant_fact_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default=DecisionPointStatus.OPEN.value)
    opened_sim_time: Mapped[float] = mapped_column(Float)
    deadline_sim_time: Mapped[float | None] = mapped_column(Float)
    closed_sim_time: Mapped[float | None] = mapped_column(Float)
    opened_at: Mapped[datetime] = created_at_col()
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class InstructorNote(Base):
    __tablename__ = "instructor_notes"

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="SET NULL")
    )
    sim_time: Mapped[float] = mapped_column(Float)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
