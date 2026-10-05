"""Message creation and server-side delivery scheduling.

Every message produces one MessageDelivery per recipient, decided independently by the
CommunicationDegradationEngine. Delayed deliveries are persisted with a *simulation-time*
schedule and released by the scenario engine's tick - delays are real server-side
behaviour, never a front-end effect, and survive reconnects and API restarts.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    ActorType,
    ChannelStatus,
    DeliveryStatus,
    DisruptionType,
    EventVisibility,
    SenderType,
    TransformationType,
)
from app.models.messaging import CommunicationDisruption, Message, MessageDelivery
from app.models.room import CommunicationChannel, Participant, SimulationRoom
from app.scenario.clock import Clock, wall_at
from app.services.audit import record_event
from app.services.degradation import (
    IMMEDIATE_THRESHOLD_SECONDS,
    ChannelView,
    CommunicationDegradationEngine,
    DegradationRules,
    DeliveryContext,
    DisruptionView,
    path_available,
)


@dataclass
class MessageSpec:
    title: str
    content: str
    source: str
    source_reliability: str
    priority: str
    importance_weight: int
    rules: DegradationRules
    channel_key: str | None = None
    fact_key: str | None = None
    fact_value: str | None = None
    location_key: str | None = None
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    variants: list[dict[str, Any]] = field(default_factory=list)
    event_reliability: float = 1.0
    sender_type: str = SenderType.SYSTEM.value
    sender_id: uuid.UUID | None = None
    scenario_event_id: uuid.UUID | None = None
    injected_conflict: bool = False
    # Force this variant for every recipient (instructor conflict injection).
    forced_variant_key: str | None = None
    # Bypass degradation entirely (system notices).
    bypass_degradation: bool = False
    # Skip probabilistic effects (jitter/random loss) but still honour channel state and
    # active disruptions - used for explicit instructor injections.
    deterministic: bool = False


def channel_view(c: CommunicationChannel) -> ChannelView:
    return ChannelView(
        id=str(c.id),
        key=c.key,
        name=c.name,
        status=c.status,
        reliability=c.reliability,
        latency_ms=c.latency_ms,
        fallback_key=c.fallback_channel_key,
    )


def disruption_view(d: CommunicationDisruption) -> DisruptionView:
    return DisruptionView(
        id=str(d.id),
        type=d.disruption_type,
        target_participant_ids=set(d.target_participant_ids or []),
        target_channel_ids=set(d.target_channel_ids or []),
        config=dict(d.configuration or {}),
    )


def trainee_message_view(
    delivery: MessageDelivery, message: Message, channel: CommunicationChannel | None
) -> dict[str, Any]:
    """Participant-safe view: only what this participant actually received.

    Deliberately excludes the server-side label (M101...), fact keys and truth fields so
    gaps in numbering cannot reveal dropped messages.
    """
    return {
        "id": str(delivery.id),
        "title": delivery.delivered_title or message.title,
        "content": delivery.delivered_content or message.canonical_content,
        "source": delivery.delivered_source or message.source,
        "reliability": delivery.delivered_source_reliability or message.source_reliability,
        "priority": message.priority,
        "channel_key": channel.key if channel else None,
        "channel_name": channel.name if channel else "System",
        "sender_type": message.sender_type,
        "location_key": message.location_key,
        "report_sim_time": message.created_sim_time,
        "received_sim_time": delivery.actual_delivery_sim_time,
        "acknowledged": delivery.acknowledged_sim_time is not None,
    }


class DeliveryService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.degradation = CommunicationDegradationEngine()

    # ------------------------------------------------------------------ loading

    async def channels(self, room_id: uuid.UUID) -> list[CommunicationChannel]:
        result = await self.session.scalars(
            select(CommunicationChannel).where(CommunicationChannel.room_id == room_id)
        )
        return list(result.all())

    async def active_disruptions(self, room_id: uuid.UUID) -> list[CommunicationDisruption]:
        result = await self.session.scalars(
            select(CommunicationDisruption).where(
                CommunicationDisruption.room_id == room_id,
                CommunicationDisruption.is_active.is_(True),
            )
        )
        return list(result.all())

    @staticmethod
    def blacked_out(disruptions: list[CommunicationDisruption]) -> tuple[bool, set[str]]:
        """(everyone_blacked_out, participant ids under blackout)."""
        everyone = False
        ids: set[str] = set()
        for d in disruptions:
            if d.disruption_type != DisruptionType.BLACKOUT:
                continue
            if not d.target_participant_ids:
                everyone = True
            ids.update(d.target_participant_ids or [])
        return everyone, ids

    # ----------------------------------------------------------------- creation

    async def create_message(
        self,
        room: SimulationRoom,
        spec: MessageSpec,
        recipients: list[Participant],
        sim: float,
        *,
        actor_id: uuid.UUID | None = None,
    ) -> Message:
        channels = await self.channels(room.id)
        by_key = {c.key: c for c in channels}
        views = {c.key: channel_view(c) for c in channels}
        channel = by_key.get(spec.channel_key) if spec.channel_key else None

        room.message_seq += 1
        message = Message(
            room_id=room.id,
            label=f"M{room.message_seq}",
            scenario_event_id=spec.scenario_event_id,
            sender_type=spec.sender_type,
            sender_id=spec.sender_id,
            channel_id=channel.id if channel else None,
            title=spec.title,
            canonical_content=spec.content,
            source=spec.source,
            source_reliability=spec.source_reliability,
            priority=spec.priority,
            importance_weight=spec.importance_weight,
            fact_key=spec.fact_key,
            fact_value=spec.fact_value,
            location_key=spec.location_key,
            is_injected_conflict=spec.injected_conflict,
            created_sim_time=sim,
        )
        self.session.add(message)
        await self.session.flush()

        await record_event(
            self.session,
            room.id,
            "message.created",
            {
                "message_id": str(message.id),
                "label": message.label,
                "title": message.title,
                "content": message.canonical_content,
                "source": message.source,
                "source_reliability": message.source_reliability,
                "priority": message.priority,
                "channel_key": channel.key if channel else None,
                "fact_key": message.fact_key,
                "fact_value": message.fact_value,
                "importance_weight": message.importance_weight,
                "recipient_ids": [str(p.id) for p in recipients],
                "injected_conflict": spec.injected_conflict,
            },
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.ENGINE,
            sim_time=sim,
        )

        disruptions = await self.active_disruptions(room.id)
        dviews = [disruption_view(d) for d in disruptions]
        consumed: set[str] = set()
        wall_now = self.clock.now()

        variants = list(spec.variants)
        for participant in recipients:
            if spec.bypass_degradation:
                override: dict[str, Any] | None = {"action": "deliver"}
            elif spec.forced_variant_key:
                override = {"action": "variant", "variant": spec.forced_variant_key}
            elif spec.deterministic:
                override = {"action": "deliver"}
            else:
                override = spec.overrides.get(participant.assigned_role or "")
            ctx = DeliveryContext(
                message_id=str(message.id),
                participant_id=str(participant.id),
                role_key=participant.assigned_role,
                channel=views.get(channel.key) if channel else None,
                channels_by_key=views,
                disruptions=[] if spec.bypass_degradation else dviews,
                rules=spec.rules,
                room_seed=room.seed,
                override=override,
                variants=variants,
                fact_key=spec.fact_key,
                event_reliability=spec.event_reliability,
            )
            plan = self.degradation.evaluate(ctx)
            consumed.update(plan.consumed_disruption_ids)

            variant = plan.variant or {}
            eff_channel = by_key.get(plan.effective_channel.key) if plan.effective_channel else None
            delivery = MessageDelivery(
                message_id=message.id,
                room_id=room.id,
                participant_id=participant.id,
                channel_id=eff_channel.id if eff_channel else None,
                delivery_status=plan.status.value,
                delivered_title=variant.get("title") or message.title,
                delivered_content=variant.get("content") or message.canonical_content,
                delivered_fact_value=variant.get("fact_value") or message.fact_value,
                delivered_source=variant.get("source") or message.source,
                delivered_source_reliability=variant.get("source_reliability")
                or message.source_reliability,
                reliability_score=plan.reliability_score,
                delay_seconds=0.0 if plan.held else plan.delay_seconds,
                transformation_type=plan.transformation_type.value,
                transformation_metadata=plan.metadata(),
            )
            self.session.add(delivery)
            base = {
                "message_id": str(message.id),
                "label": message.label,
                "participant_id": str(participant.id),
                "callsign": participant.callsign,
                "transformation_type": plan.transformation_type.value,
                "reasons": plan.reasons,
            }
            if plan.is_dropped:
                delivery.reliability_score = 0.0
                await record_event(
                    self.session,
                    room.id,
                    "message.dropped",
                    base,
                    actor_type=ActorType.ENGINE,
                    sim_time=sim,
                )
            elif plan.held:
                await record_event(
                    self.session,
                    room.id,
                    "message.held",
                    base,
                    actor_type=ActorType.ENGINE,
                    sim_time=sim,
                )
            elif plan.is_immediate:
                delivery.scheduled_sim_time = sim
                delivery.scheduled_delivery_at = wall_now
                await self.session.flush()
                await self._mark_delivered(room, delivery, message, eff_channel, participant, sim)
            else:
                delivery.scheduled_sim_time = round(sim + plan.delay_seconds, 3)
                delivery.scheduled_delivery_at = wall_at(
                    room, delivery.scheduled_sim_time, wall_now
                )
                await record_event(
                    self.session,
                    room.id,
                    "message.delayed",
                    {
                        **base,
                        "delay_seconds": plan.delay_seconds,
                        "scheduled_sim_time": delivery.scheduled_sim_time,
                    },
                    actor_type=ActorType.ENGINE,
                    sim_time=sim,
                )

        # "Drop next message" disruptions are consumed once per message.
        for d in disruptions:
            if str(d.id) in consumed:
                remaining = int((d.configuration or {}).get("remaining", 0)) - 1
                d.configuration = {**(d.configuration or {}), "remaining": max(0, remaining)}
                if remaining <= 0:
                    d.is_active = False
                    d.end_sim_time = sim
                    d.end_time = wall_now
                    await record_event(
                        self.session,
                        room.id,
                        "disruption.ended",
                        {
                            "disruption_id": str(d.id),
                            "disruption_type": d.disruption_type,
                            "reason": "consumed",
                        },
                        actor_type=ActorType.ENGINE,
                        sim_time=sim,
                    )
        await self.session.flush()
        return message

    async def _mark_delivered(
        self,
        room: SimulationRoom,
        delivery: MessageDelivery,
        message: Message,
        channel: CommunicationChannel | None,
        participant: Participant | None,
        sim: float,
    ) -> None:
        delivery.delivery_status = (
            DeliveryStatus.ALTERED.value
            if delivery.transformation_type == TransformationType.VARIANT
            else DeliveryStatus.DELIVERED.value
        )
        delivery.actual_delivery_sim_time = sim
        delivery.actual_delivery_at = self.clock.now()
        delivery.delay_seconds = round(max(0.0, sim - message.created_sim_time), 2)
        await record_event(
            self.session,
            room.id,
            "message.delivered",
            trainee_message_view(delivery, message, channel),
            actor_type=ActorType.ENGINE,
            sim_time=sim,
            visibility=EventVisibility.PARTICIPANTS,
            targets=[delivery.participant_id],
        )
        await record_event(
            self.session,
            room.id,
            "delivery.completed",
            {
                "message_id": str(message.id),
                "label": message.label,
                "delivery_id": str(delivery.id),
                "participant_id": str(delivery.participant_id),
                "callsign": participant.callsign if participant else None,
                "status": delivery.delivery_status,
                "delay_seconds": delivery.delay_seconds,
                "transformation_type": delivery.transformation_type,
                "channel_key": channel.key if channel else None,
            },
            actor_type=ActorType.ENGINE,
            sim_time=sim,
        )

    # ----------------------------------------------------------------- the tick

    async def deliver_due(self, room: SimulationRoom, sim: float) -> int:
        """Deliver every scheduled delivery whose simulation time has come."""
        rows = (
            await self.session.execute(
                select(MessageDelivery, Message)
                .join(Message, Message.id == MessageDelivery.message_id)
                .where(
                    MessageDelivery.room_id == room.id,
                    MessageDelivery.delivery_status.in_(
                        [DeliveryStatus.PENDING, DeliveryStatus.DELAYED]
                    ),
                    MessageDelivery.scheduled_sim_time.is_not(None),
                    MessageDelivery.scheduled_sim_time <= sim,
                )
                .order_by(MessageDelivery.scheduled_sim_time)
                .with_for_update(of=MessageDelivery, skip_locked=True)
            )
        ).all()
        if not rows:
            return 0
        channels = await self.channels(room.id)
        by_id = {c.id: c for c in channels}
        views = {c.key: channel_view(c) for c in channels}
        disruptions = await self.active_disruptions(room.id)
        everyone_out, out_ids = self.blacked_out(disruptions)
        participants = {
            p.id: p
            for p in (
                await self.session.scalars(
                    select(Participant).where(Participant.room_id == room.id)
                )
            ).all()
        }
        delivered = 0
        for delivery, message in rows:
            channel = by_id.get(delivery.channel_id) if delivery.channel_id else None
            blacked = everyone_out or str(delivery.participant_id) in out_ids
            if blacked or (channel is not None and channel.status == ChannelStatus.OFFLINE):
                path = path_available(views.get(channel.key) if channel else None, views, blacked)
                if path is None:
                    delivery.scheduled_sim_time = None
                    delivery.transformation_metadata = {
                        **(delivery.transformation_metadata or {}),
                        "held_at": sim,
                    }
                    await record_event(
                        self.session,
                        room.id,
                        "message.held",
                        {
                            "message_id": str(message.id),
                            "label": message.label,
                            "participant_id": str(delivery.participant_id),
                            "reasons": ["Path lost before delivery - held until restored"],
                        },
                        actor_type=ActorType.ENGINE,
                        sim_time=sim,
                    )
                    continue
                if isinstance(path, ChannelView):
                    channel = next(c for c in channels if c.key == path.key)
                    delivery.channel_id = channel.id
            await self._mark_delivered(
                room, delivery, message, channel, participants.get(delivery.participant_id), sim
            )
            delivered += 1
        await self.session.flush()
        return delivered

    async def release_held(self, room: SimulationRoom, sim: float) -> int:
        """Re-schedule held deliveries whose path has been restored."""
        rows = (
            await self.session.execute(
                select(MessageDelivery, Message)
                .join(Message, Message.id == MessageDelivery.message_id)
                .where(
                    MessageDelivery.room_id == room.id,
                    MessageDelivery.delivery_status == DeliveryStatus.DELAYED,
                    MessageDelivery.scheduled_sim_time.is_(None),
                )
                .with_for_update(of=MessageDelivery, skip_locked=True)
            )
        ).all()
        if not rows:
            return 0
        channels = await self.channels(room.id)
        by_id = {c.id: c for c in channels}
        views = {c.key: channel_view(c) for c in channels}
        disruptions = await self.active_disruptions(room.id)
        everyone_out, out_ids = self.blacked_out(disruptions)
        released = 0
        for delivery, message in rows:
            original = by_id.get(message.channel_id) if message.channel_id else None
            blacked = everyone_out or str(delivery.participant_id) in out_ids
            path = path_available(views.get(original.key) if original else None, views, blacked)
            if path is None:
                continue
            latency = 0.0
            if isinstance(path, ChannelView):
                target = next(c for c in channels if c.key == path.key)
                delivery.channel_id = target.id
                latency = target.latency_ms / 1000.0
                if original is not None and target.id != original.id:
                    delivery.transformation_metadata = {
                        **(delivery.transformation_metadata or {}),
                        "rerouted_via": target.key,
                    }
            delivery.scheduled_sim_time = round(sim + latency, 3)
            delivery.scheduled_delivery_at = wall_at(
                room, delivery.scheduled_sim_time, self.clock.now()
            )
            delivery.transformation_metadata = {
                **(delivery.transformation_metadata or {}),
                "released_at": sim,
            }
            await record_event(
                self.session,
                room.id,
                "message.released",
                {
                    "message_id": str(message.id),
                    "label": message.label,
                    "participant_id": str(delivery.participant_id),
                    "scheduled_sim_time": delivery.scheduled_sim_time,
                },
                actor_type=ActorType.ENGINE,
                sim_time=sim,
            )
            released += 1
        await self.session.flush()
        if released:
            # Anything released with (near) zero latency is delivered in the same tick.
            await self.deliver_due(room, sim + IMMEDIATE_THRESHOLD_SECONDS - 0.001)
        return released

    async def fail_undelivered(self, room: SimulationRoom, sim: float) -> int:
        """At exercise end, anything still in flight never arrived."""
        rows = (
            await self.session.execute(
                select(MessageDelivery, Message)
                .join(Message, Message.id == MessageDelivery.message_id)
                .where(
                    MessageDelivery.room_id == room.id,
                    MessageDelivery.delivery_status.in_(
                        [DeliveryStatus.PENDING, DeliveryStatus.DELAYED]
                    ),
                )
            )
        ).all()
        for delivery, message in rows:
            delivery.delivery_status = DeliveryStatus.FAILED.value
            delivery.transformation_metadata = {
                **(delivery.transformation_metadata or {}),
                "failed_at": sim,
                "undelivered_reason": "Exercise ended before delivery",
            }
            await record_event(
                self.session,
                room.id,
                "message.failed",
                {
                    "message_id": str(message.id),
                    "label": message.label,
                    "participant_id": str(delivery.participant_id),
                },
                actor_type=ActorType.ENGINE,
                sim_time=sim,
            )
        return len(rows)
