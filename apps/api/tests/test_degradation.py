"""Unit tests for the CommunicationDegradationEngine (pure logic, no I/O)."""

from app.models.enums import DeliveryStatus, TransformationType
from app.services.degradation import (
    ChannelView,
    CommunicationDegradationEngine,
    DegradationRules,
    DeliveryContext,
    DisruptionView,
    resolve_rules,
)

ENGINE = CommunicationDegradationEngine()
NO_RANDOM = DegradationRules(0.0, 0.0, 0.0, 0.0, 0.0)
CMD = ChannelView("c1", "command", "Command Net", "ONLINE", 0.95, 500, "backup")
BACKUP_OFF = ChannelView("c2", "backup", "Backup HF", "OFFLINE", 0.75, 4000)
BACKUP_ON = ChannelView("c2", "backup", "Backup HF", "ONLINE", 0.75, 4000)
VARIANTS = [{"key": "unusable", "fact_value": "unusable", "content": "Bridge unusable"}]


def ctx(**kw: object) -> DeliveryContext:
    base: dict[str, object] = {
        "message_id": "m1",
        "participant_id": "p1",
        "role_key": "alpha",
        "channel": CMD,
        "channels_by_key": {"command": CMD, "backup": BACKUP_OFF},
        "disruptions": [],
        "rules": NO_RANDOM,
        "room_seed": 42,
        "variants": VARIANTS,
        "fact_key": "bridge",
    }
    base.update(kw)
    return DeliveryContext(**base)  # type: ignore[arg-type]


def test_normal_delivery_is_immediate() -> None:
    plan = ENGINE.evaluate(ctx())
    assert plan.status == DeliveryStatus.DELIVERED
    assert plan.is_immediate and plan.delay_seconds == 0.5


def test_override_drop() -> None:
    plan = ENGINE.evaluate(ctx(override={"action": "drop"}))
    assert plan.status == DeliveryStatus.DROPPED
    assert plan.transformation_type == TransformationType.DROP
    assert "dropped" in plan.reasons[0]


def test_override_delay_is_scheduled() -> None:
    plan = ENGINE.evaluate(ctx(override={"action": "delay", "seconds": 90}))
    assert plan.status == DeliveryStatus.DELAYED
    assert plan.delay_seconds == 90.5
    assert plan.transformation_type == TransformationType.DELAY


def test_override_variant_alters_content() -> None:
    plan = ENGINE.evaluate(ctx(override={"action": "variant", "variant": "unusable"}))
    assert plan.status == DeliveryStatus.ALTERED
    assert plan.variant is not None and plan.variant["fact_value"] == "unusable"
    assert plan.transformation_type == TransformationType.VARIANT


def test_offline_channel_without_fallback_holds_message() -> None:
    offline = ChannelView("c1", "command", "Command Net", "OFFLINE", 0.0, 500, "backup")
    plan = ENGINE.evaluate(
        ctx(channel=offline, channels_by_key={"command": offline, "backup": BACKUP_OFF})
    )
    assert plan.held and plan.status == DeliveryStatus.DELAYED
    assert plan.transformation_type == TransformationType.CHANNEL_UNAVAILABLE


def test_offline_channel_reroutes_via_fallback() -> None:
    offline = ChannelView("c1", "command", "Command Net", "OFFLINE", 0.0, 500, "backup")
    plan = ENGINE.evaluate(
        ctx(channel=offline, channels_by_key={"command": offline, "backup": BACKUP_ON})
    )
    assert not plan.held
    assert plan.effective_channel is not None and plan.effective_channel.key == "backup"
    assert plan.transformation_type == TransformationType.REROUTED
    assert plan.delay_seconds == 4.0


def test_blackout_holds_for_targeted_participant_only() -> None:
    blackout = DisruptionView("d1", "BLACKOUT", {"p1"}, set(), {})
    assert ENGINE.evaluate(ctx(disruptions=[blackout])).held
    assert not ENGINE.evaluate(ctx(participant_id="p2", disruptions=[blackout])).held


def test_drop_next_disruption_is_consumed() -> None:
    dropout = DisruptionView("d1", "DROPOUT", {"p1"}, set(), {"remaining": 1})
    plan = ENGINE.evaluate(ctx(disruptions=[dropout]))
    assert plan.status == DeliveryStatus.DROPPED
    assert plan.consumed_disruption_ids == ["d1"]


def test_delay_disruption_on_channel_adds_delay() -> None:
    delay = DisruptionView("d1", "DELAY", set(), {"c1"}, {"delay_seconds": 60})
    plan = ENGINE.evaluate(ctx(disruptions=[delay]))
    assert plan.status == DeliveryStatus.DELAYED
    assert plan.delay_seconds == 60.5


def test_conflict_injection_disruption_selects_variant() -> None:
    inj = DisruptionView(
        "d1", "CONFLICT_INJECTION", {"p1"}, set(), {"fact_key": "bridge", "variant_key": "unusable"}
    )
    assert ENGINE.evaluate(ctx(disruptions=[inj])).status == DeliveryStatus.ALTERED


def test_outcome_is_deterministic_for_same_seed() -> None:
    rules = DegradationRules(0.5, 0.3, 0.3, 30.0, 0.5)
    a = [ENGINE.evaluate(ctx(rules=rules, message_id=f"m{i}")) for i in range(50)]
    b = [ENGINE.evaluate(ctx(rules=rules, message_id=f"m{i}")) for i in range(50)]
    assert [(p.status, p.delay_seconds) for p in a] == [(p.status, p.delay_seconds) for p in b]


def test_each_recipient_is_evaluated_independently() -> None:
    rules = DegradationRules(0.5, 0.3, 0.0, 30.0, 0.0)
    outcomes = {
        (ENGINE.evaluate(ctx(rules=rules, participant_id=f"p{i}")).status) for i in range(40)
    }
    assert {DeliveryStatus.DELIVERED, DeliveryStatus.DROPPED} <= outcomes


def test_drop_probability_roughly_matches_configuration() -> None:
    rules = DegradationRules(0.0, 0.25, 0.0, 0.0, 0.0)
    drops = sum(
        ENGINE.evaluate(ctx(rules=rules, message_id=f"m{i}")).status == DeliveryStatus.DROPPED
        for i in range(2000)
    )
    assert 400 < drops < 600


def test_difficulty_defaults_and_overrides() -> None:
    rules = resolve_rules("ADVANCED", {"drop_probability": 0.0}, {"delay_probability": 0.9})
    assert rules.drop_probability == 0.0
    assert rules.delay_probability == 0.9
    assert rules.conflict_probability == 0.10
