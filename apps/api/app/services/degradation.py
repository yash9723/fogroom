"""CommunicationDegradationEngine - decides, per recipient, what happens to a message.

Pure logic (no I/O) so it is easy to test and reason about. Decisions are deterministic:
the random generator is seeded from (room seed, message id, participant id), so the same
inputs always produce the same outcome. Replay never re-runs this engine - it reads the
recorded MessageDelivery rows.

Evaluation order (first matching rule wins for drop; effects accumulate for delay):
  1. Scenario override for the recipient's role ("drop", "delay", "variant", "deliver")
  2. Instructor DROPOUT disruptions ("drop next N messages", drop probability)
  3. Probabilistic loss (difficulty/scenario drop probability + channel unreliability)
  4. Conflicting variant (override, CONFLICT_INJECTION disruption, or conflict probability)
  5. Channel availability (OFFLINE -> reroute via fallback channel, else hold until restored;
     participant BLACKOUT -> hold)
  6. Delay = channel latency + override delay + DELAY disruptions + random jitter
"""

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import ChannelStatus, DeliveryStatus, DisruptionType, TransformationType

# Messages arriving within this many simulation seconds are treated as immediate.
IMMEDIATE_THRESHOLD_SECONDS = 1.0


@dataclass(frozen=True)
class DegradationRules:
    delay_probability: float = 0.25
    drop_probability: float = 0.05
    conflict_probability: float = 0.05
    jitter_seconds: float = 20.0
    # Extra drop probability per unit of channel unreliability (1 - reliability).
    channel_loss_factor: float = 0.25

    def merged(self, overrides: dict[str, Any] | None) -> "DegradationRules":
        if not overrides:
            return self
        values = {**self.__dict__}
        for key, value in overrides.items():
            if key in values and value is not None:
                values[key] = float(value)
        return DegradationRules(**values)


DIFFICULTY_DEFAULTS: dict[str, DegradationRules] = {
    "BEGINNER": DegradationRules(0.10, 0.02, 0.00, 10.0, 0.10),
    "INTERMEDIATE": DegradationRules(0.25, 0.05, 0.05, 20.0, 0.25),
    "ADVANCED": DegradationRules(0.40, 0.10, 0.10, 40.0, 0.40),
}


def resolve_rules(
    difficulty: str, scenario_rules: dict[str, Any] | None, event_rules: dict[str, Any] | None
) -> DegradationRules:
    """Difficulty defaults <- scenario overrides <- per-event overrides."""
    base = DIFFICULTY_DEFAULTS.get(difficulty, DIFFICULTY_DEFAULTS["INTERMEDIATE"])
    return base.merged(scenario_rules).merged(event_rules)


@dataclass(frozen=True)
class ChannelView:
    id: str
    key: str
    name: str
    status: str
    reliability: float
    latency_ms: int
    fallback_key: str | None = None


@dataclass
class DisruptionView:
    id: str
    type: str
    target_participant_ids: set[str]
    target_channel_ids: set[str]
    config: dict[str, Any]

    def targets_participant(self, participant_id: str) -> bool:
        return not self.target_participant_ids or participant_id in self.target_participant_ids

    def targets_channel(self, channel_id: str | None) -> bool:
        if not self.target_channel_ids:
            return True
        return channel_id is not None and channel_id in self.target_channel_ids


@dataclass
class DeliveryContext:
    message_id: str
    participant_id: str
    role_key: str | None
    channel: ChannelView | None
    channels_by_key: dict[str, ChannelView]
    disruptions: list[DisruptionView]
    rules: DegradationRules
    room_seed: int
    override: dict[str, Any] | None = None
    variants: list[dict[str, Any]] = field(default_factory=list)
    fact_key: str | None = None
    event_reliability: float = 1.0


@dataclass
class DeliveryPlan:
    status: DeliveryStatus
    delay_seconds: float = 0.0
    held: bool = False
    variant: dict[str, Any] | None = None
    transformation_type: TransformationType = TransformationType.NONE
    reliability_score: float = 1.0
    effective_channel: ChannelView | None = None
    reasons: list[str] = field(default_factory=list)
    consumed_disruption_ids: list[str] = field(default_factory=list)

    @property
    def is_dropped(self) -> bool:
        return self.status == DeliveryStatus.DROPPED

    @property
    def is_immediate(self) -> bool:
        return (
            not self.held
            and not self.is_dropped
            and self.delay_seconds < IMMEDIATE_THRESHOLD_SECONDS
        )

    def metadata(self) -> dict[str, Any]:
        data: dict[str, Any] = {"reasons": self.reasons}
        if self.variant:
            data["variant_key"] = self.variant.get("key")
            data["variant_fact_value"] = self.variant.get("fact_value")
        if self.effective_channel:
            data["effective_channel_key"] = self.effective_channel.key
        if self.consumed_disruption_ids:
            data["disruption_ids"] = self.consumed_disruption_ids
        return data


def seeded_rng(room_seed: int, message_id: str, participant_id: str) -> random.Random:
    digest = hashlib.sha256(f"{room_seed}:{message_id}:{participant_id}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


class CommunicationDegradationEngine:
    """Stateless evaluator. `evaluate` must be called once per (message, recipient)."""

    def evaluate(self, ctx: DeliveryContext) -> DeliveryPlan:
        rng = seeded_rng(ctx.room_seed, ctx.message_id, ctx.participant_id)
        reasons: list[str] = []
        override = ctx.override or {}
        action = override.get("action")
        channel = ctx.channel
        channel_id = channel.id if channel else None

        # 1. Explicit scenario rule: drop.
        if action == "drop":
            return DeliveryPlan(
                status=DeliveryStatus.DROPPED,
                transformation_type=TransformationType.DROP,
                effective_channel=channel,
                reliability_score=0.0,
                reasons=[f"Scenario rule: message dropped for role '{ctx.role_key}'"],
            )

        # 2. Instructor dropout disruptions.
        consumed: list[str] = []
        for d in ctx.disruptions:
            if d.type != DisruptionType.DROPOUT:
                continue
            if not (d.targets_participant(ctx.participant_id) and d.targets_channel(channel_id)):
                continue
            remaining = d.config.get("remaining")
            if remaining is not None and int(remaining) > 0:
                consumed.append(d.id)
                return DeliveryPlan(
                    status=DeliveryStatus.DROPPED,
                    transformation_type=TransformationType.DROP,
                    effective_channel=channel,
                    reliability_score=0.0,
                    reasons=["Instructor disruption: drop next message"],
                    consumed_disruption_ids=consumed,
                )
            probability = float(d.config.get("drop_probability", 0.0))
            if probability > 0 and rng.random() < probability:
                return DeliveryPlan(
                    status=DeliveryStatus.DROPPED,
                    transformation_type=TransformationType.DROP,
                    effective_channel=channel,
                    reliability_score=0.0,
                    reasons=[f"Instructor dropout disruption (p={probability:.2f})"],
                )

        # Effective reliability of the path (channel x event x reliability reductions).
        effective_reliability = (channel.reliability if channel else 1.0) * ctx.event_reliability
        for d in ctx.disruptions:
            # Room-wide reductions are already applied to channel state; only
            # participant-scoped reductions are applied here.
            if (
                d.type == DisruptionType.RELIABILITY_REDUCTION
                and d.target_participant_ids
                and d.targets_participant(ctx.participant_id)
                and d.targets_channel(channel_id)
            ):
                effective_reliability *= float(d.config.get("factor", 0.5))
                reasons.append("Reliability reduction disruption active")
        effective_reliability = max(0.0, min(1.0, effective_reliability))

        # 3. Probabilistic loss - only when no explicit scenario rule applies.
        if not override:
            p_drop = (
                ctx.rules.drop_probability
                + (1.0 - effective_reliability) * ctx.rules.channel_loss_factor
            )
            if p_drop > 0 and rng.random() < p_drop:
                return DeliveryPlan(
                    status=DeliveryStatus.DROPPED,
                    transformation_type=TransformationType.DROP,
                    effective_channel=channel,
                    reliability_score=0.0,
                    reasons=[
                        f"Lost in transit (p={p_drop:.2f}, path reliability {effective_reliability:.2f})"
                    ],
                )

        # 4. Conflicting variant.
        variant: dict[str, Any] | None = None
        if action == "variant":
            variant = _find_variant(ctx.variants, override.get("variant"))
            if variant:
                reasons.append(f"Scenario rule: conflicting variant '{variant.get('key')}'")
        if variant is None:
            for d in ctx.disruptions:
                if d.type != DisruptionType.CONFLICT_INJECTION or not d.targets_participant(
                    ctx.participant_id
                ):
                    continue
                if d.config.get("fact_key") and d.config.get("fact_key") == ctx.fact_key:
                    variant = _find_variant(ctx.variants, d.config.get("variant_key"))
                    if variant:
                        reasons.append("Instructor conflict injection")
                        break
        # Short-circuit order matters: rng is only consumed when variants exist (determinism).
        if (
            variant is None
            and not override
            and ctx.variants
            and rng.random() < ctx.rules.conflict_probability
        ):
            variant = rng.choice(ctx.variants)
            reasons.append(f"Random conflict (p={ctx.rules.conflict_probability:.2f})")

        # 5. Channel availability.
        held = False
        rerouted = False
        effective_channel = channel
        blackout = any(
            d.type == DisruptionType.BLACKOUT and d.targets_participant(ctx.participant_id)
            for d in ctx.disruptions
        )
        if blackout:
            held = True
            reasons.append("Participant communications blackout - held until restored")
        elif channel is not None and channel.status == ChannelStatus.OFFLINE:
            fallback = (
                ctx.channels_by_key.get(channel.fallback_key) if channel.fallback_key else None
            )
            if fallback is not None and fallback.status != ChannelStatus.OFFLINE:
                effective_channel = fallback
                rerouted = True
                reasons.append(f"{channel.name} offline - rerouted via {fallback.name}")
            else:
                held = True
                reasons.append(f"{channel.name} offline - held until a path is restored")

        # 6. Delay.
        delay = (effective_channel.latency_ms / 1000.0) if effective_channel else 0.0
        if action == "delay":
            extra = float(override.get("seconds", 0))
            delay += extra
            reasons.append(f"Scenario rule: delayed {extra:.0f}s")
        for d in ctx.disruptions:
            if (
                d.type == DisruptionType.DELAY
                and d.targets_participant(ctx.participant_id)
                and d.targets_channel(effective_channel.id if effective_channel else None)
            ):
                extra = float(d.config.get("delay_seconds", 30))
                delay += extra
                reasons.append(f"Delay disruption +{extra:.0f}s")
        if (
            not override
            and ctx.rules.delay_probability > 0
            and rng.random() < ctx.rules.delay_probability
        ):
            jitter = rng.uniform(0.25, 1.0) * ctx.rules.jitter_seconds
            delay += jitter
            reasons.append(f"Network jitter +{jitter:.0f}s")

        if effective_channel is not None and effective_channel is not channel:
            effective_reliability = min(effective_reliability, effective_channel.reliability)

        if variant is not None:
            transformation = TransformationType.VARIANT
        elif held:
            transformation = TransformationType.CHANNEL_UNAVAILABLE
        elif rerouted:
            transformation = TransformationType.REROUTED
        elif delay >= IMMEDIATE_THRESHOLD_SECONDS and any(
            "delay" in r.lower() or "jitter" in r.lower() for r in reasons
        ):
            transformation = TransformationType.DELAY
        else:
            transformation = TransformationType.NONE

        immediate = not held and delay < IMMEDIATE_THRESHOLD_SECONDS
        if immediate:
            status = DeliveryStatus.ALTERED if variant else DeliveryStatus.DELIVERED
        else:
            status = DeliveryStatus.DELAYED

        return DeliveryPlan(
            status=status,
            delay_seconds=round(delay, 2),
            held=held,
            variant=variant,
            transformation_type=transformation,
            reliability_score=round(effective_reliability, 3),
            effective_channel=effective_channel,
            reasons=reasons,
            consumed_disruption_ids=consumed,
        )


def _find_variant(variants: list[dict[str, Any]], key: Any) -> dict[str, Any] | None:
    for v in variants:
        if v.get("key") == key:
            return v
    return None


def path_available(
    channel: ChannelView | None,
    channels_by_key: dict[str, ChannelView],
    participant_blacked_out: bool,
) -> ChannelView | None | bool:
    """Return the channel a held message can now travel on, True for channel-less
    messages, or None if no path exists yet."""
    if participant_blacked_out:
        return None
    if channel is None:
        return True
    if channel.status != ChannelStatus.OFFLINE:
        return channel
    fallback = channels_by_key.get(channel.fallback_key) if channel.fallback_key else None
    if fallback is not None and fallback.status != ChannelStatus.OFFLINE:
        return fallback
    return None
