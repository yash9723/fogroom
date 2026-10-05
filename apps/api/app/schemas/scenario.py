"""Scenario template schemas - used for the REST API, the seed data and room snapshots."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ChannelStatus,
    Difficulty,
    DisruptionType,
    Priority,
    ScenarioEventType,
    SourceReliability,
    TriggerType,
)

Key = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9_\-]+$")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectiveSchema(_Model):
    key: str = Key
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class RoleSchema(_Model):
    key: str = Key
    name: str = Field(min_length=1, max_length=120)
    callsign: str = Field(min_length=1, max_length=40)
    team: str = Field(default="Response Cell", max_length=60)
    description: str = Field(default="", max_length=2000)
    objectives: list[str] = Field(default_factory=list)


class ChannelSchema(_Model):
    key: str = Key
    name: str = Field(min_length=1, max_length=80)
    channel_type: str = Field(default="VOICE", max_length=40)
    initial_status: ChannelStatus = ChannelStatus.ONLINE
    reliability: float = Field(default=0.95, ge=0, le=1)
    latency_ms: int = Field(default=500, ge=0, le=600_000)
    weight: float = Field(default=1.0, gt=0, le=10)
    fallback_channel_key: str | None = None


class PhaseSchema(_Model):
    key: str = Key
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    starts_at_seconds: int = Field(default=0, ge=0)


class VariantSchema(_Model):
    key: str = Key
    fact_value: str = Field(min_length=1, max_length=120)
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    source: str | None = Field(default=None, max_length=120)
    source_reliability: SourceReliability | None = None


class OverrideRule(_Model):
    action: Literal["drop", "delay", "variant", "deliver"]
    seconds: float | None = Field(default=None, ge=0, le=7200)
    variant: str | None = None


class DegradationSchema(_Model):
    delay_probability: float | None = Field(default=None, ge=0, le=1)
    drop_probability: float | None = Field(default=None, ge=0, le=1)
    conflict_probability: float | None = Field(default=None, ge=0, le=1)
    jitter_seconds: float | None = Field(default=None, ge=0, le=3600)
    channel_loss_factor: float | None = Field(default=None, ge=0, le=1)


class TargetingRules(_Model):
    recipients: Literal["all"] | list[str] = "all"
    overrides: dict[str, OverrideRule] = Field(default_factory=dict)
    degradation: DegradationSchema | None = None


class EventEffects(_Model):
    # CHANNEL_CHANGE
    channel_key: str | None = None
    status: ChannelStatus | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0, le=600_000)
    # DISRUPTION
    disruption_type: DisruptionType | None = None
    duration_seconds: int | None = Field(default=None, ge=1, le=7200)
    severity: int = Field(default=2, ge=1, le=3)
    target_roles: list[str] = Field(default_factory=list)
    target_channel_keys: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class EventTemplateSchema(_Model):
    key: str = Key
    event_type: ScenarioEventType
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=4000)
    trigger_type: TriggerType = TriggerType.TIME
    scheduled_offset_seconds: int | None = Field(default=None, ge=0)
    trigger_decision_key: str | None = None
    phase_key: str | None = None
    channel_key: str | None = None
    priority: Priority = Priority.NORMAL
    source: str = Field(default="Coordination Centre", max_length=120)
    source_reliability: SourceReliability = SourceReliability.MEDIUM
    reliability: float = Field(default=1.0, ge=0, le=1)
    importance_weight: int = Field(default=1, ge=1, le=5)
    fact_key: str | None = Field(default=None, max_length=60)
    fact_value: str | None = Field(default=None, max_length=120)
    location_key: str | None = Field(default=None, max_length=60)
    targeting_rules: TargetingRules = Field(default_factory=TargetingRules)
    variants: list[VariantSchema] = Field(default_factory=list)
    effects: EventEffects | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionOptionSchema(_Model):
    key: str = Key
    label: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    truth_alignment: int = Field(default=50, ge=0, le=100)


class DecisionPointSchema(_Model):
    key: str = Key
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=4000)
    options: list[DecisionOptionSchema] = Field(default_factory=list)
    trigger_type: TriggerType = TriggerType.TIME
    opens_at_seconds: int | None = Field(default=None, ge=0)
    trigger_decision_key: str | None = None
    deadline_seconds: int = Field(default=120, ge=10, le=3600)
    allow_custom: bool = False
    require_rationale: bool = True
    target_roles: list[str] = Field(default_factory=list)
    phase_key: str | None = None
    critical: bool = False
    relevant_fact_keys: list[str] = Field(default_factory=list)


class FactTimelineEntry(_Model):
    from_seconds: int = Field(ge=0)
    value: str = Field(min_length=1, max_length=120)


class FactSchema(_Model):
    key: str = Key
    label: str = Field(min_length=1, max_length=120)
    timeline: list[FactTimelineEntry] = Field(min_length=1)


class LocationSchema(_Model):
    key: str = Key
    name: str = Field(min_length=1, max_length=120)
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=1000)
    kind: str = Field(default="site", max_length=40)


class InitialConditions(_Model):
    facts: list[FactSchema] = Field(default_factory=list)
    locations: list[LocationSchema] = Field(default_factory=list)
    map: dict[str, Any] = Field(default_factory=dict)


class ScenarioBase(_Model):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    difficulty: Difficulty = Difficulty.INTERMEDIATE
    estimated_duration_minutes: int = Field(default=15, ge=1, le=600)
    category: str = Field(default="General", max_length=80)
    briefing: str = Field(default="", max_length=8000)
    objectives: list[ObjectiveSchema] = Field(default_factory=list)
    initial_conditions: InitialConditions = Field(default_factory=InitialConditions)
    degradation_rules: DegradationSchema = Field(default_factory=DegradationSchema)
    roles: list[RoleSchema] = Field(default_factory=list)
    channels: list[ChannelSchema] = Field(default_factory=list)
    phases: list[PhaseSchema] = Field(default_factory=list)
    events: list[EventTemplateSchema] = Field(default_factory=list)
    decision_points: list[DecisionPointSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> "ScenarioBase":  # noqa: C901 - flat validation list
        def unique(items: list[Any], what: str) -> set[str]:
            keys = [i.key for i in items]
            dupes = {k for k in keys if keys.count(k) > 1}
            if dupes:
                raise ValueError(f"Duplicate {what} keys: {sorted(dupes)}")
            return set(keys)

        roles = unique(self.roles, "role")
        channels = unique(self.channels, "channel")
        phases = unique(self.phases, "phase")
        unique(self.events, "event")
        decisions = unique(self.decision_points, "decision point")
        locations = unique(self.initial_conditions.locations, "location")

        for ch in self.channels:
            if ch.fallback_channel_key and ch.fallback_channel_key not in channels:
                raise ValueError(
                    f"Channel '{ch.key}' has unknown fallback '{ch.fallback_channel_key}'"
                )
        for ev in self.events:
            where = f"event '{ev.key}'"
            if ev.channel_key and ev.channel_key not in channels:
                raise ValueError(f"{where}: unknown channel '{ev.channel_key}'")
            if ev.phase_key and ev.phase_key not in phases:
                raise ValueError(f"{where}: unknown phase '{ev.phase_key}'")
            if ev.location_key and ev.location_key not in locations:
                raise ValueError(f"{where}: unknown location '{ev.location_key}'")
            if ev.trigger_type == TriggerType.TIME and ev.scheduled_offset_seconds is None:
                raise ValueError(f"{where}: TIME trigger requires scheduled_offset_seconds")
            if (
                ev.trigger_type == TriggerType.AFTER_DECISION
                and ev.trigger_decision_key not in decisions
            ):
                raise ValueError(
                    f"{where}: AFTER_DECISION trigger requires a valid trigger_decision_key"
                )
            recipients = ev.targeting_rules.recipients
            if isinstance(recipients, list) and not set(recipients) <= roles:
                raise ValueError(
                    f"{where}: unknown recipient roles {sorted(set(recipients) - roles)}"
                )
            variant_keys = {v.key for v in ev.variants}
            for role, rule in ev.targeting_rules.overrides.items():
                if role not in roles:
                    raise ValueError(f"{where}: override for unknown role '{role}'")
                if rule.action == "variant" and rule.variant not in variant_keys:
                    raise ValueError(
                        f"{where}: override references unknown variant '{rule.variant}'"
                    )
            if ev.event_type == ScenarioEventType.CHANNEL_CHANGE and (
                not ev.effects or ev.effects.channel_key not in channels
            ):
                raise ValueError(f"{where}: CHANNEL_CHANGE requires effects.channel_key")
            if ev.event_type == ScenarioEventType.DISRUPTION:
                if not ev.effects or not ev.effects.disruption_type:
                    raise ValueError(f"{where}: DISRUPTION requires effects.disruption_type")
                if not set(ev.effects.target_channel_keys) <= channels:
                    raise ValueError(f"{where}: unknown disruption channels")
                if not set(ev.effects.target_roles) <= roles:
                    raise ValueError(f"{where}: unknown disruption roles")
        for dp in self.decision_points:
            where = f"decision point '{dp.key}'"
            if not set(dp.target_roles) <= roles:
                raise ValueError(f"{where}: unknown target roles")
            if not dp.options and not dp.allow_custom:
                raise ValueError(f"{where}: needs options or allow_custom")
            option_keys = [o.key for o in dp.options]
            if len(option_keys) != len(set(option_keys)):
                raise ValueError(f"{where}: duplicate option keys")
            if dp.trigger_type == TriggerType.TIME and dp.opens_at_seconds is None:
                raise ValueError(f"{where}: TIME trigger requires opens_at_seconds")
            if (
                dp.trigger_type == TriggerType.AFTER_DECISION
                and dp.trigger_decision_key not in decisions
            ):
                raise ValueError(
                    f"{where}: AFTER_DECISION trigger requires a valid trigger_decision_key"
                )
        return self


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioOut(ScenarioBase):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    is_published: bool = True
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ScenarioSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    difficulty: str
    estimated_duration_minutes: int
    category: str
    role_count: int
    channel_count: int
    event_count: int
    decision_count: int
    created_at: datetime
    updated_at: datetime
