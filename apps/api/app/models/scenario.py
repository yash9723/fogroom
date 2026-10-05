"""Scenario templates: the designer-authored blueprint of an exercise."""

import uuid
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_check, uuid_pk
from app.models.enums import Difficulty, Priority, ScenarioEventType, SourceReliability, TriggerType


class ScenarioTemplate(TimestampMixin, Base):
    __tablename__ = "scenario_templates"
    __table_args__ = (enum_check("difficulty", Difficulty),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(16), default=Difficulty.INTERMEDIATE.value)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=15)
    category: Mapped[str] = mapped_column(String(80), default="General")
    briefing: Mapped[str] = mapped_column(Text, default="")
    # [{"key": "incomplete_info", "title": "...", "description": "..."}]
    objectives: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # {"map": {...}, "facts": [...], "locations": [...]}  - truth model & map layout
    initial_conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Overrides for difficulty defaults: delay_probability, drop_probability, ...
    degradation_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    roles: Mapped[list["ScenarioRole"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioRole.sort_order"
    )
    channels: Mapped[list["ScenarioChannel"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioChannel.sort_order",
    )
    phases: Mapped[list["ScenarioPhase"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioPhase.starts_at_seconds",
    )
    events: Mapped[list["ScenarioEventTemplate"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioEventTemplate.scheduled_offset_seconds",
    )
    decision_points: Mapped[list["ScenarioDecisionPoint"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioDecisionPoint.opens_at_seconds",
    )


class ScenarioRole(Base):
    __tablename__ = "scenario_roles"
    __table_args__ = (UniqueConstraint("scenario_id", "key", name="uq_scenario_roles_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    callsign: Mapped[str] = mapped_column(String(40))
    team: Mapped[str] = mapped_column(String(60), default="Response Cell")
    description: Mapped[str] = mapped_column(Text, default="")
    objectives: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    scenario: Mapped[ScenarioTemplate] = relationship(back_populates="roles")


class ScenarioChannel(Base):
    __tablename__ = "scenario_channels"
    __table_args__ = (UniqueConstraint("scenario_id", "key", name="uq_scenario_channels_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    channel_type: Mapped[str] = mapped_column(String(40), default="VOICE")
    initial_status: Mapped[str] = mapped_column(String(16), default="ONLINE")
    reliability: Mapped[float] = mapped_column(Float, default=0.95)
    latency_ms: Mapped[int] = mapped_column(Integer, default=500)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    fallback_channel_key: Mapped[str | None] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    scenario: Mapped[ScenarioTemplate] = relationship(back_populates="channels")


class ScenarioPhase(Base):
    __tablename__ = "scenario_phases"
    __table_args__ = (UniqueConstraint("scenario_id", "key", name="uq_scenario_phases_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at_seconds: Mapped[int] = mapped_column(Integer, default=0)

    scenario: Mapped[ScenarioTemplate] = relationship(back_populates="phases")


class ScenarioEventTemplate(Base):
    __tablename__ = "scenario_event_templates"
    __table_args__ = (
        UniqueConstraint("scenario_template_id", "key", name="uq_scenario_event_templates_key"),
        enum_check("event_type", ScenarioEventType),
        enum_check("trigger_type", TriggerType),
        enum_check("priority", Priority),
        enum_check("source_reliability", SourceReliability),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    event_type: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    trigger_type: Mapped[str] = mapped_column(String(16), default=TriggerType.TIME.value)
    scheduled_offset_seconds: Mapped[int | None] = mapped_column(Integer)
    trigger_decision_key: Mapped[str | None] = mapped_column(String(60))
    phase_key: Mapped[str | None] = mapped_column(String(40))
    channel_key: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(16), default=Priority.NORMAL.value)
    source: Mapped[str] = mapped_column(String(120), default="Coordination Centre")
    source_reliability: Mapped[str] = mapped_column(
        String(8), default=SourceReliability.MEDIUM.value
    )
    # Delivery reliability of this event (0-1) - multiplies channel reliability.
    reliability: Mapped[float] = mapped_column(Float, default=1.0)
    importance_weight: Mapped[int] = mapped_column(Integer, default=1)
    fact_key: Mapped[str | None] = mapped_column(String(60))
    fact_value: Mapped[str | None] = mapped_column(String(120))
    location_key: Mapped[str | None] = mapped_column(String(60))
    # {"recipients": "all" | [role keys], "overrides": {role: {"action": ...}},
    #  "degradation": {"delay_probability": .., "drop_probability": .., ...}}
    targeting_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Controlled conflicting variants: [{"key", "fact_value", "title", "content", "source", ...}]
    variants: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Side effects for CHANNEL_CHANGE / DISRUPTION events.
    effects: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    scenario: Mapped[ScenarioTemplate] = relationship(back_populates="events")


class ScenarioDecisionPoint(Base):
    __tablename__ = "scenario_decision_points"
    __table_args__ = (
        UniqueConstraint("scenario_id", "key", name="uq_scenario_decision_points_key"),
        enum_check("trigger_type", TriggerType),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    # [{"key", "label", "description", "truth_alignment": 0-100}]
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    trigger_type: Mapped[str] = mapped_column(String(16), default=TriggerType.TIME.value)
    opens_at_seconds: Mapped[int | None] = mapped_column(Integer)
    trigger_decision_key: Mapped[str | None] = mapped_column(String(60))
    deadline_seconds: Mapped[int] = mapped_column(Integer, default=120)
    allow_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    require_rationale: Mapped[bool] = mapped_column(Boolean, default=True)
    target_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)  # [] = everyone
    phase_key: Mapped[str | None] = mapped_column(String(40))
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    # Fact keys a well-informed decision depends on (used for AAR analysis).
    relevant_fact_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)

    scenario: Mapped[ScenarioTemplate] = relationship(back_populates="decision_points")
