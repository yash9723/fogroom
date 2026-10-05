"""Request schemas for rooms, live controls and trainee actions."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ChannelStatus,
    DisruptionType,
    Priority,
    ScenarioEventType,
    SourceReliability,
)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomCreate(_In):
    scenario_id: uuid.UUID
    name: str | None = Field(default=None, max_length=200)
    time_scale: float = Field(default=1.0, ge=0.25, le=20)


class DemoLaunchIn(_In):
    time_scale: float = Field(default=1.0, ge=0.25, le=20)


class JoinByCodeIn(_In):
    room_code: str = Field(min_length=3, max_length=16)


class ParticipantUpdate(_In):
    role_key: str | None = Field(default=None, max_length=40)
    callsign: str | None = Field(default=None, max_length=40)


class ReadyIn(_In):
    ready: bool = True


class AdvanceClockIn(_In):
    to_sim_seconds: float = Field(ge=0, le=86_400)


class ChannelUpdate(_In):
    status: ChannelStatus | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0, le=600_000)
    restore: bool = False
    reason: str | None = Field(default=None, max_length=200)


class DisruptionCreate(_In):
    disruption_type: DisruptionType
    target_participant_ids: list[uuid.UUID] = Field(default_factory=list)
    target_channel_ids: list[uuid.UUID] = Field(default_factory=list)
    severity: int = Field(default=2, ge=1, le=3)
    duration_seconds: float | None = Field(default=None, ge=1, le=7200)
    delay_seconds: float | None = Field(default=None, ge=1, le=3600)
    drop_probability: float | None = Field(default=None, ge=0, le=1)
    drop_next: int | None = Field(default=None, ge=1, le=20)
    factor: float | None = Field(default=None, ge=0.05, le=1)
    fact_key: str | None = Field(default=None, max_length=60)
    variant_key: str | None = Field(default=None, max_length=60)

    @model_validator(mode="after")
    def _check(self) -> "DisruptionCreate":
        t = self.disruption_type
        if t == DisruptionType.DELAY and self.delay_seconds is None:
            self.delay_seconds = 30.0 * self.severity
        if t == DisruptionType.DROPOUT and self.drop_next is None and self.drop_probability is None:
            self.drop_next = 1
        if t == DisruptionType.RELIABILITY_REDUCTION and self.factor is None:
            self.factor = {1: 0.8, 2: 0.6, 3: 0.4}[self.severity]
        if t == DisruptionType.CHANNEL_FAILURE and not self.target_channel_ids:
            raise ValueError("Channel failure requires target_channel_ids")
        if t == DisruptionType.CONFLICT_INJECTION and not (self.fact_key and self.variant_key):
            raise ValueError("Conflict injection disruption requires fact_key and variant_key")
        return self

    def config(self) -> dict[str, object]:
        cfg: dict[str, object] = {}
        if self.delay_seconds is not None:
            cfg["delay_seconds"] = self.delay_seconds
        if self.drop_next is not None:
            cfg["remaining"] = self.drop_next
        if self.drop_probability is not None:
            cfg["drop_probability"] = self.drop_probability
        if self.factor is not None:
            cfg["factor"] = self.factor
        if self.fact_key:
            cfg["fact_key"] = self.fact_key
        if self.variant_key:
            cfg["variant_key"] = self.variant_key
        return cfg


class CustomEventIn(_In):
    event_type: ScenarioEventType = ScenarioEventType.INFORMATION
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    channel_key: str | None = Field(default=None, max_length=40)
    priority: Priority = Priority.NORMAL
    source: str = Field(default="Exercise Control", max_length=120)
    source_reliability: SourceReliability = SourceReliability.MEDIUM
    importance_weight: int = Field(default=1, ge=1, le=5)
    fact_key: str | None = Field(default=None, max_length=60)
    fact_value: str | None = Field(default=None, max_length=120)
    location_key: str | None = Field(default=None, max_length=60)
    target_participant_ids: list[uuid.UUID] = Field(default_factory=list)


class TriggerEventIn(_In):
    template_key: str | None = Field(default=None, max_length=60)
    custom: CustomEventIn | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "TriggerEventIn":
        if bool(self.template_key) == bool(self.custom):
            raise ValueError("Provide exactly one of template_key or custom")
        return self


class NoticeIn(_In):
    title: str = Field(default="Exercise notice", min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)
    channel_key: str | None = Field(default=None, max_length=40)
    priority: Priority = Priority.NORMAL
    target_participant_ids: list[uuid.UUID] = Field(default_factory=list)


class ConflictIn(_In):
    fact_key: str = Field(min_length=1, max_length=60)
    fact_value: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="Unverified report", max_length=120)
    source_reliability: SourceReliability = SourceReliability.LOW
    priority: Priority = Priority.HIGH
    channel_key: str | None = Field(default=None, max_length=40)
    location_key: str | None = Field(default=None, max_length=60)
    target_participant_ids: list[uuid.UUID] = Field(default_factory=list)


class DecisionSubmitIn(_In):
    selected_option: str | None = Field(default=None, max_length=60)
    decision_text: str | None = Field(default=None, max_length=2000)
    rationale: str | None = Field(default=None, max_length=4000)
    confidence: int = Field(ge=0, le=100)


class TeamMessageIn(_In):
    message: str = Field(min_length=1, max_length=1000)
    channel_key: str = Field(min_length=1, max_length=40)
    recipient_participant_id: uuid.UUID | None = None


class NoteIn(_In):
    content: str = Field(min_length=1, max_length=2000)
    participant_id: uuid.UUID | None = None
