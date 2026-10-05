"""Scenario events, messages and the all-important per-recipient deliveries."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, enum_check, uuid_pk
from app.models.enums import (
    DeliveryStatus,
    DisruptionType,
    Priority,
    SenderType,
    SourceReliability,
    TransformationType,
)


class ScenarioEvent(Base):
    """An event that actually fired in a room (scheduled or instructor-triggered)."""

    __tablename__ = "scenario_events"
    __table_args__ = (
        Index(
            "uq_scenario_events_room_template_key",
            "room_id",
            "template_key",
            unique=True,
            postgresql_where=text("template_key IS NOT NULL"),
        ),
        Index("ix_scenario_events_room_sim", "room_id", "sim_time"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    event_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_event_templates.id", ondelete="SET NULL")
    )
    template_key: Mapped[str | None] = mapped_column(String(60))
    event_type: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    truth_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sim_time: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = created_at_col()
    triggered_at: Mapped[datetime] = created_at_col()
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    trigger_source: Mapped[str] = mapped_column(String(16), default="SCHEDULE")


class Message(Base):
    """Canonical (truth) version of a piece of information."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("room_id", "label", name="uq_messages_room_label"),
        Index("ix_messages_room_sim", "room_id", "created_sim_time"),
        enum_check("sender_type", SenderType),
        enum_check("priority", Priority),
        enum_check("source_reliability", SourceReliability),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(16))  # human-readable id, e.g. "M101"
    scenario_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_events.id", ondelete="SET NULL"), index=True
    )
    sender_type: Mapped[str] = mapped_column(String(16), default=SenderType.SYSTEM.value)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communication_channels.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200))
    canonical_content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120))
    source_reliability: Mapped[str] = mapped_column(
        String(8), default=SourceReliability.MEDIUM.value
    )
    priority: Mapped[str] = mapped_column(String(16), default=Priority.NORMAL.value)
    importance_weight: Mapped[int] = mapped_column(Integer, default=1)
    fact_key: Mapped[str | None] = mapped_column(String(60), index=True)
    fact_value: Mapped[str | None] = mapped_column(String(120))
    location_key: Mapped[str | None] = mapped_column(String(60))
    is_injected_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    created_sim_time: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = created_at_col()

    deliveries: Mapped[list["MessageDelivery"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class MessageDelivery(Base):
    """What one participant actually experienced for one message.

    One row per (message, recipient). Dropped/failed rows are kept forever so the
    AAR can say "M101 was dropped for Bravo"; trainees can never read them.
    """

    __tablename__ = "message_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "participant_id", name="uq_message_deliveries_msg_participant"
        ),
        Index("ix_deliveries_due", "room_id", "delivery_status", "scheduled_sim_time"),
        Index("ix_deliveries_participant_time", "participant_id", "actual_delivery_sim_time"),
        enum_check("delivery_status", DeliveryStatus),
        enum_check("transformation_type", TransformationType),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE")
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE")
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communication_channels.id", ondelete="SET NULL")
    )
    delivery_status: Mapped[str] = mapped_column(String(16))
    delivered_title: Mapped[str | None] = mapped_column(String(200))
    delivered_content: Mapped[str | None] = mapped_column(Text)
    delivered_fact_value: Mapped[str | None] = mapped_column(String(120))
    delivered_source: Mapped[str | None] = mapped_column(String(120))
    delivered_source_reliability: Mapped[str | None] = mapped_column(String(8))
    scheduled_sim_time: Mapped[float | None] = mapped_column(Float)  # NULL = held (channel down)
    actual_delivery_sim_time: Mapped[float | None] = mapped_column(Float)
    scheduled_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delay_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0)
    transformation_type: Mapped[str] = mapped_column(
        String(24), default=TransformationType.NONE.value
    )
    transformation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    acknowledged_sim_time: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = created_at_col()

    message: Mapped[Message] = relationship(back_populates="deliveries")


class TeamMessage(Base):
    __tablename__ = "team_messages"
    __table_args__ = (Index("ix_team_messages_room_sim", "room_id", "sim_time"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    sender_participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE")
    )
    recipient_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE")
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communication_channels.id", ondelete="SET NULL")
    )
    message: Mapped[str] = mapped_column(Text)
    sim_time: Mapped[float] = mapped_column(Float)
    # Participant ids that actually received it (blackouts exclude recipients).
    delivered_to: Mapped[list[str]] = mapped_column(JSONB, default=list)
    delivery_status: Mapped[str] = mapped_column(String(16), default=DeliveryStatus.DELIVERED.value)
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_at_col()


class CommunicationDisruption(Base):
    __tablename__ = "communication_disruptions"
    __table_args__ = (
        Index("ix_disruptions_room_active", "room_id", "is_active"),
        enum_check("disruption_type", DisruptionType),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_rooms.id", ondelete="CASCADE")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    disruption_type: Mapped[str] = mapped_column(String(32))
    target_participant_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)  # [] = all
    target_channel_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)  # [] = all
    severity: Mapped[int] = mapped_column(Integer, default=2)  # 1 low .. 3 high
    start_sim_time: Mapped[float] = mapped_column(Float)
    end_sim_time: Mapped[float | None] = mapped_column(Float)  # actual end
    planned_end_sim_time: Mapped[float | None] = mapped_column(Float)
    start_time: Mapped[datetime] = created_at_col()
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # e.g. {"delay_seconds": 60} | {"drop_probability": .5, "remaining": 1} | {"factor": .5}
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(16), default="INSTRUCTOR")
