"""ScenarioEngine - the simulation core.

Owns the simulation clock, the scenario event queue, decision points, communication
channels and disruptions, message creation (delegated to DeliveryService) and periodic
metric snapshots. Every meaningful action is appended to the audit event stream.

All public mutators expect the room row to be locked (`lock_room`) and leave committing
(`commit_and_publish`) to the caller, so each API action / tick is one transaction.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict, not_found
from app.models.aar import MetricSnapshot
from app.models.decision import Decision
from app.models.enums import (
    MESSAGE_EVENT_TYPES,
    ActorType,
    ChannelStatus,
    DecisionPointStatus,
    DisruptionType,
    EventVisibility,
    Priority,
    RoomStatus,
    ScenarioEventType,
    SenderType,
    SourceReliability,
    TriggerType,
)
from app.models.messaging import CommunicationDisruption, MessageDelivery, ScenarioEvent
from app.models.room import (
    ChannelStateChange,
    CommunicationChannel,
    Participant,
    RoomDecisionPoint,
    SimulationRoom,
)
from app.scenario.clock import (
    Clock,
    SystemClock,
    pause_clock,
    resume_clock,
    sim_now,
    start_clock,
    stop_clock,
)
from app.services import metrics as m
from app.services.audit import record_event
from app.services.degradation import DegradationRules, resolve_rules
from app.services.delivery import DeliveryService, MessageSpec
from app.services.information_state import InformationStateService, truth_value_at

METRIC_INTERVAL_SECONDS = 30.0


def trainee_decision_point(dp: RoomDecisionPoint) -> dict[str, Any]:
    """Decision point as shown to trainees - the truth_alignment rubric is stripped."""
    return {
        "id": str(dp.id),
        "key": dp.key,
        "title": dp.title,
        "prompt": dp.prompt,
        "options": [
            {"key": o["key"], "label": o["label"], "description": o.get("description", "")}
            for o in dp.options
        ],
        "allow_custom": dp.allow_custom,
        "require_rationale": dp.require_rationale,
        "status": dp.status,
        "opened_sim_time": dp.opened_sim_time,
        "deadline_sim_time": dp.deadline_sim_time,
        "closed_sim_time": dp.closed_sim_time,
        "critical": dp.critical,
    }


class ScenarioEngine:
    def __init__(self, session: AsyncSession, clock: Clock | None = None) -> None:
        self.session = session
        self.clock = clock or SystemClock()
        self.delivery = DeliveryService(session, self.clock)

    # ----------------------------------------------------------------- loading

    async def lock_room(self, room_id: uuid.UUID) -> SimulationRoom:
        room = await self.session.scalar(
            select(SimulationRoom)
            .where(SimulationRoom.id == room_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if room is None:
            raise not_found("ROOM_NOT_FOUND", "Room not found.")
        return room

    def now_sim(self, room: SimulationRoom) -> float:
        return sim_now(room, self.clock.now())

    async def participants(self, room: SimulationRoom) -> list[Participant]:
        result = await self.session.scalars(
            select(Participant)
            .where(Participant.room_id == room.id)
            .order_by(Participant.joined_at)
        )
        return list(result.all())

    async def channels(self, room: SimulationRoom) -> list[CommunicationChannel]:
        result = await self.session.scalars(
            select(CommunicationChannel)
            .where(CommunicationChannel.room_id == room.id)
            .order_by(CommunicationChannel.sort_order)
        )
        return list(result.all())

    @staticmethod
    def snapshot(room: SimulationRoom) -> dict[str, Any]:
        return room.scenario_snapshot or {}

    def rules_for(
        self, room: SimulationRoom, event: dict[str, Any] | None = None
    ) -> DegradationRules:
        snap = self.snapshot(room)
        event_rules = ((event or {}).get("targeting_rules") or {}).get("degradation")
        return resolve_rules(
            snap.get("difficulty", "INTERMEDIATE"), snap.get("degradation_rules"), event_rules
        )

    @staticmethod
    def resolve_recipients(participants: list[Participant], recipients: Any) -> list[Participant]:
        if not recipients or recipients == "all":
            return list(participants)
        wanted = set(recipients)
        return [p for p in participants if p.assigned_role in wanted]

    @staticmethod
    def _require(room: SimulationRoom, *statuses: RoomStatus) -> None:
        if room.status not in statuses:
            code = "ROOM_NOT_RUNNING" if RoomStatus.RUNNING in statuses else "INVALID_ROOM_STATE"
            raise conflict(
                code,
                f"Action not allowed while the exercise is {room.status}.",
                {"status": room.status, "allowed": [s.value for s in statuses]},
            )

    # --------------------------------------------------------------- lifecycle

    async def start(self, room: SimulationRoom, actor_id: uuid.UUID) -> None:
        self._require(room, RoomStatus.LOBBY)
        participants = await self.participants(room)
        if not participants:
            raise AppError(
                "NO_PARTICIPANTS", "At least one trainee must join before starting.", 409
            )
        roles = [r["key"] for r in self.snapshot(room).get("roles", [])]
        taken = {p.assigned_role for p in participants if p.assigned_role}
        free = [r for r in roles if r not in taken]
        for p in participants:
            if not p.assigned_role and free:
                p.assigned_role = free.pop(0)

        now = self.clock.now()
        start_clock(room, now)
        room.status = RoomStatus.RUNNING.value
        for channel in await self.channels(room):
            self.session.add(
                ChannelStateChange(
                    room_id=room.id,
                    channel_id=channel.id,
                    sim_time=0.0,
                    status=channel.status,
                    reliability=channel.reliability,
                    latency_ms=channel.latency_ms,
                    reason="Initial state",
                )
            )
        await record_event(
            self.session,
            room.id,
            "simulation.started",
            {
                "participants": [
                    {"id": str(p.id), "callsign": p.callsign, "role": p.assigned_role}
                    for p in participants
                ]
            },
            actor_id=actor_id,
            actor_type=ActorType.USER,
            sim_time=0.0,
            visibility=EventVisibility.ALL,
        )
        await self.process(room, 0.0)

    async def pause(self, room: SimulationRoom, actor_id: uuid.UUID) -> float:
        self._require(room, RoomStatus.RUNNING)
        sim = pause_clock(room, self.clock.now())
        room.status = RoomStatus.PAUSED.value
        await record_event(
            self.session,
            room.id,
            "simulation.paused",
            {},
            actor_id=actor_id,
            actor_type=ActorType.USER,
            sim_time=sim,
            visibility=EventVisibility.ALL,
        )
        return sim

    async def resume(self, room: SimulationRoom, actor_id: uuid.UUID) -> float:
        self._require(room, RoomStatus.PAUSED)
        sim = resume_clock(room, self.clock.now())
        room.status = RoomStatus.RUNNING.value
        await record_event(
            self.session,
            room.id,
            "simulation.resumed",
            {},
            actor_id=actor_id,
            actor_type=ActorType.USER,
            sim_time=sim,
            visibility=EventVisibility.ALL,
        )
        return sim

    async def end(
        self, room: SimulationRoom, actor_id: uuid.UUID | None, reason: str = "Ended by instructor"
    ) -> float:
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        # Bring everything due up to now before freezing history.
        sim = self.now_sim(room)
        if room.status == RoomStatus.RUNNING:
            await self.process(room, sim)
        for dp in await self._decision_points(room):
            if dp.status == DecisionPointStatus.OPEN:
                await self._close_decision_point(room, dp, sim, reason="Exercise ended")
        for d in await self.delivery.active_disruptions(room.id):
            await self.end_disruption(room, d, None, sim, reason="Exercise ended")
        await self.delivery.fail_undelivered(room, sim)
        await self._metric_snapshot(room, sim)
        stop_clock(room, self.clock.now())
        room.final_sim_seconds = sim
        room.sim_anchor_seconds = sim
        room.status = RoomStatus.COMPLETED.value
        room.ended_at = self.clock.now()
        await record_event(
            self.session,
            room.id,
            "simulation.completed",
            {"reason": reason},
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
            sim_time=sim,
            visibility=EventVisibility.ALL,
        )
        return sim

    async def advance_clock(
        self, room: SimulationRoom, to_sim: float, actor_id: uuid.UUID
    ) -> float:
        """Fast-forward: step through every scheduled moment in order, so history is the
        same as if the time had elapsed naturally."""
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        current = self.now_sim(room)
        if to_sim <= current:
            raise AppError("INVALID_TIME", "Can only advance the clock forwards.", 422)
        await record_event(
            self.session,
            room.id,
            "clock.advanced",
            {"from": current, "to": to_sim},
            actor_id=actor_id,
            actor_type=ActorType.USER,
            sim_time=current,
            visibility=EventVisibility.ALL,
        )
        cursor = current
        guard = 0
        while cursor < to_sim and guard < 500:
            guard += 1
            nxt = await self._next_scheduled_after(room, cursor)
            step = min(nxt, to_sim) if nxt is not None else to_sim
            await self.process(room, step)
            cursor = step
        room.sim_anchor_seconds = to_sim
        if room.status == RoomStatus.RUNNING:
            room.anchor_at = self.clock.now()
        return to_sim

    async def _next_scheduled_after(self, room: SimulationRoom, t: float) -> float | None:
        snap = self.snapshot(room)
        candidates: list[float] = []
        for ev in snap.get("events", []):
            off = ev.get("scheduled_offset_seconds")
            if ev.get("trigger_type", "TIME") == TriggerType.TIME and off is not None and off > t:
                candidates.append(float(off))
        for dp in snap.get("decision_points", []):
            off = dp.get("opens_at_seconds")
            if dp.get("trigger_type", "TIME") == TriggerType.TIME and off is not None and off > t:
                candidates.append(float(off))
        for dp in await self._decision_points(room):
            if (
                dp.status == DecisionPointStatus.OPEN
                and dp.deadline_sim_time
                and dp.deadline_sim_time > t
            ):
                candidates.append(dp.deadline_sim_time)
        nxt_delivery = await self.session.scalar(
            select(MessageDelivery.scheduled_sim_time)
            .where(
                MessageDelivery.room_id == room.id,
                MessageDelivery.scheduled_sim_time > t,
                MessageDelivery.actual_delivery_sim_time.is_(None),
                MessageDelivery.delivery_status.in_(["PENDING", "DELAYED"]),
            )
            .order_by(MessageDelivery.scheduled_sim_time)
            .limit(1)
        )
        if nxt_delivery is not None:
            candidates.append(float(nxt_delivery))
        for d in await self.delivery.active_disruptions(room.id):
            if d.planned_end_sim_time is not None and d.planned_end_sim_time > t:
                candidates.append(d.planned_end_sim_time)
        return min(candidates) if candidates else None

    # -------------------------------------------------------------------- tick

    async def tick(self, room_id: uuid.UUID) -> float | None:
        room = await self.lock_room(room_id)
        if room.status != RoomStatus.RUNNING:
            return None
        sim = self.now_sim(room)
        await self.process(room, sim)
        return sim

    async def process(self, room: SimulationRoom, sim: float) -> None:
        """Advance scenario state to simulation time `sim` (idempotent)."""
        snap = self.snapshot(room)
        await self._update_phase(room, snap, sim)

        for d in await self.delivery.active_disruptions(room.id):
            if d.planned_end_sim_time is not None and d.planned_end_sim_time <= sim:
                await self.end_disruption(room, d, None, sim, reason="Scheduled end")

        fired = set(
            (
                await self.session.scalars(
                    select(ScenarioEvent.template_key).where(
                        ScenarioEvent.room_id == room.id, ScenarioEvent.template_key.is_not(None)
                    )
                )
            ).all()
        )
        time_events = sorted(
            (
                e
                for e in snap.get("events", [])
                if e.get("trigger_type", "TIME") == TriggerType.TIME
                and e.get("scheduled_offset_seconds") is not None
                and e["scheduled_offset_seconds"] <= sim
                and e["key"] not in fired
            ),
            key=lambda e: e["scheduled_offset_seconds"],
        )
        for ev in time_events:
            await self.fire_event(room, ev, sim, actor_id=None, source="SCHEDULE")
            fired.add(ev["key"])

        points = {dp.key: dp for dp in await self._decision_points(room)}
        for tmpl in snap.get("decision_points", []):
            if (
                tmpl.get("trigger_type", "TIME") == TriggerType.TIME
                and tmpl.get("opens_at_seconds") is not None
                and tmpl["opens_at_seconds"] <= sim
                and tmpl["key"] not in points
            ):
                points[tmpl["key"]] = await self.open_decision_point(room, tmpl, sim, actor_id=None)

        for dp in list(points.values()):
            if (
                dp.status == DecisionPointStatus.OPEN
                and dp.deadline_sim_time is not None
                and dp.deadline_sim_time <= sim
            ):
                await self._close_decision_point(room, dp, sim, reason="Deadline reached")

        closed = {k for k, dp in points.items() if dp.status == DecisionPointStatus.CLOSED}
        for ev in snap.get("events", []):
            if (
                ev.get("trigger_type") == TriggerType.AFTER_DECISION
                and ev.get("trigger_decision_key") in closed
                and ev["key"] not in fired
            ):
                await self.fire_event(room, ev, sim, actor_id=None, source="DECISION")
                fired.add(ev["key"])
        for tmpl in snap.get("decision_points", []):
            if (
                tmpl.get("trigger_type") == TriggerType.AFTER_DECISION
                and tmpl.get("trigger_decision_key") in closed
                and tmpl["key"] not in points
            ):
                points[tmpl["key"]] = await self.open_decision_point(room, tmpl, sim, actor_id=None)

        await self.delivery.release_held(room, sim)
        await self.delivery.deliver_due(room, sim)

        if sim - room.last_metrics_sim_time >= METRIC_INTERVAL_SECONDS:
            await self._metric_snapshot(room, sim)

    async def _update_phase(self, room: SimulationRoom, snap: dict[str, Any], sim: float) -> None:
        phases = sorted(snap.get("phases", []), key=lambda p: p["starts_at_seconds"])
        current = None
        for phase in phases:
            if phase["starts_at_seconds"] <= sim:
                current = phase
        if current and current["key"] != room.current_phase_key:
            room.current_phase_key = current["key"]
            await record_event(
                self.session,
                room.id,
                "phase.changed",
                {
                    "key": current["key"],
                    "name": current["name"],
                    "description": current.get("description", ""),
                },
                actor_type=ActorType.ENGINE,
                sim_time=sim,
                visibility=EventVisibility.ALL,
            )

    # ------------------------------------------------------------------ events

    def event_template(self, room: SimulationRoom, key: str) -> dict[str, Any]:
        for ev in self.snapshot(room).get("events", []):
            if ev["key"] == key:
                return dict(ev)
        raise not_found("EVENT_NOT_FOUND", f"Scenario event '{key}' not found.")

    async def fire_event(
        self,
        room: SimulationRoom,
        ev: dict[str, Any],
        sim: float,
        *,
        actor_id: uuid.UUID | None,
        source: str,
        template_key: str | None = "__from_event__",
        target_participant_ids: list[str] | None = None,
    ) -> ScenarioEvent:
        key = ev.get("key") if template_key == "__from_event__" else template_key
        facts = self.snapshot(room).get("initial_conditions", {}).get("facts", [])
        scenario_event = ScenarioEvent(
            room_id=room.id,
            template_key=key,
            event_type=ev["event_type"],
            title=ev["title"],
            content=ev.get("content", ""),
            truth_payload={
                "fact_key": ev.get("fact_key"),
                "reported_value": ev.get("fact_value"),
                "truth_value_at_event": truth_value_at(facts, ev.get("fact_key"), sim),
                "variants": [v.get("fact_value") for v in ev.get("variants", [])],
            },
            sim_time=sim,
            triggered_by=actor_id,
            trigger_source=source,
        )
        self.session.add(scenario_event)
        await self.session.flush()
        await record_event(
            self.session,
            room.id,
            "scenario.event",
            {
                "scenario_event_id": str(scenario_event.id),
                "event_key": key,
                "event_type": ev["event_type"],
                "title": ev["title"],
                "trigger_source": source,
                "truth": scenario_event.truth_payload,
            },
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.ENGINE,
            sim_time=sim,
        )

        participants = await self.participants(room)
        event_type = ev["event_type"]
        if event_type in MESSAGE_EVENT_TYPES:
            recipients = self.resolve_recipients(
                participants, (ev.get("targeting_rules") or {}).get("recipients")
            )
            if target_participant_ids:
                wanted = set(target_participant_ids)
                recipients = [p for p in participants if str(p.id) in wanted]
            spec = MessageSpec(
                title=ev["title"],
                content=ev.get("content", ""),
                source=ev.get("source", "Coordination Centre"),
                source_reliability=ev.get("source_reliability", SourceReliability.MEDIUM.value),
                priority=ev.get("priority", Priority.NORMAL.value),
                importance_weight=int(ev.get("importance_weight", 1)),
                rules=self.rules_for(room, ev),
                channel_key=ev.get("channel_key"),
                fact_key=ev.get("fact_key"),
                fact_value=ev.get("fact_value"),
                location_key=ev.get("location_key"),
                overrides=(ev.get("targeting_rules") or {}).get("overrides", {}),
                variants=ev.get("variants", []),
                event_reliability=float(ev.get("reliability", 1.0)),
                sender_type=SenderType.INSTRUCTOR.value if actor_id else SenderType.SYSTEM.value,
                sender_id=actor_id,
                scenario_event_id=scenario_event.id,
            )
            await self.delivery.create_message(room, spec, recipients, sim, actor_id=actor_id)
        elif event_type == ScenarioEventType.CHANNEL_CHANGE:
            effects = ev.get("effects") or {}
            channel = await self._channel_by_key(room, effects.get("channel_key"))
            await self.set_channel_state(
                room,
                channel,
                status=effects.get("status") or channel.status,
                reliability=effects.get("reliability"),
                latency_ms=effects.get("latency_ms"),
                reason=ev["title"],
                actor_id=actor_id,
                sim=sim,
            )
            if ev.get("content"):
                await self.system_notice(
                    room, ev["title"], ev["content"], participants, sim, scenario_event.id
                )
        elif event_type == ScenarioEventType.DISRUPTION:
            effects = ev.get("effects") or {}
            role_targets = set(effects.get("target_roles") or [])
            channel_keys = set(effects.get("target_channel_keys") or [])
            channels = await self.channels(room)
            await self.create_disruption(
                room,
                disruption_type=effects["disruption_type"],
                target_participant_ids=[
                    str(p.id) for p in participants if p.assigned_role in role_targets
                ],
                target_channel_ids=[str(c.id) for c in channels if c.key in channel_keys],
                severity=int(effects.get("severity", 2)),
                config=dict(effects.get("config") or {}),
                duration_seconds=effects.get("duration_seconds"),
                actor_id=actor_id,
                sim=sim,
                source="SCENARIO",
            )
            if ev.get("content"):
                await self.system_notice(
                    room, ev["title"], ev["content"], participants, sim, scenario_event.id
                )
        return scenario_event

    async def system_notice(
        self,
        room: SimulationRoom,
        title: str,
        content: str,
        recipients: list[Participant],
        sim: float,
        scenario_event_id: uuid.UUID | None = None,
        *,
        actor_id: uuid.UUID | None = None,
        channel_key: str | None = None,
        priority: str = Priority.NORMAL.value,
    ) -> None:
        """Out-of-band notice. Without a channel it bypasses degradation (simulated SMS
        broadcast); with a channel it travels like any other message."""
        spec = MessageSpec(
            title=title,
            content=content,
            source="Exercise Control" if actor_id else "Network Status",
            source_reliability=SourceReliability.HIGH.value,
            priority=priority,
            importance_weight=1,
            rules=self.rules_for(room),
            channel_key=channel_key,
            sender_type=SenderType.INSTRUCTOR.value if actor_id else SenderType.SYSTEM.value,
            sender_id=actor_id,
            scenario_event_id=scenario_event_id,
            bypass_degradation=channel_key is None,
            deterministic=True,
        )
        await self.delivery.create_message(room, spec, recipients, sim, actor_id=actor_id)

    async def trigger_template_event(
        self, room: SimulationRoom, key: str, actor_id: uuid.UUID
    ) -> ScenarioEvent:
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        ev = self.event_template(room, key)
        existing = await self.session.scalar(
            select(ScenarioEvent.id).where(
                ScenarioEvent.room_id == room.id, ScenarioEvent.template_key == key
            )
        )
        if existing is not None:
            raise conflict("EVENT_ALREADY_FIRED", f"Scenario event '{key}' has already fired.")
        sim = self.now_sim(room)
        result = await self.fire_event(room, ev, sim, actor_id=actor_id, source="INSTRUCTOR")
        await self.delivery.deliver_due(room, sim)
        return result

    async def trigger_custom_event(
        self, room: SimulationRoom, payload: dict[str, Any], actor_id: uuid.UUID
    ) -> ScenarioEvent:
        """Instructor-authored ad-hoc information event (goes through degradation)."""
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        sim = self.now_sim(room)
        ev = {
            "key": None,
            "event_type": payload.get("event_type", ScenarioEventType.INFORMATION.value),
            "title": payload["title"],
            "content": payload["content"],
            "channel_key": payload.get("channel_key"),
            "priority": payload.get("priority", Priority.NORMAL.value),
            "source": payload.get("source", "Exercise Control"),
            "source_reliability": payload.get("source_reliability", SourceReliability.MEDIUM.value),
            "importance_weight": payload.get("importance_weight", 1),
            "fact_key": payload.get("fact_key"),
            "fact_value": payload.get("fact_value"),
            "location_key": payload.get("location_key"),
            "targeting_rules": {"recipients": "all"},
        }
        result = await self.fire_event(
            room,
            ev,
            sim,
            actor_id=actor_id,
            source="INSTRUCTOR",
            template_key=None,
            target_participant_ids=payload.get("target_participant_ids") or None,
        )
        await self.delivery.deliver_due(room, sim)
        return result

    async def inject_conflict(
        self, room: SimulationRoom, payload: dict[str, Any], actor_id: uuid.UUID
    ) -> None:
        """Deliver a controlled conflicting report about `fact_key` to selected participants."""
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        sim = self.now_sim(room)
        participants = await self.participants(room)
        targets = set(payload.get("target_participant_ids") or [])
        recipients = [p for p in participants if not targets or str(p.id) in targets]
        if not recipients:
            raise AppError("NO_RECIPIENTS", "No matching participants for the conflict.", 422)
        spec = MessageSpec(
            title=payload["title"],
            content=payload["content"],
            source=payload.get("source", "Unverified report"),
            source_reliability=payload.get("source_reliability", SourceReliability.LOW.value),
            priority=payload.get("priority", Priority.HIGH.value),
            importance_weight=int(payload.get("importance_weight", 2)),
            rules=self.rules_for(room),
            channel_key=payload.get("channel_key"),
            fact_key=payload["fact_key"],
            fact_value=payload["fact_value"],
            location_key=payload.get("location_key"),
            overrides={},
            sender_type=SenderType.INSTRUCTOR.value,
            sender_id=actor_id,
            injected_conflict=True,
            deterministic=True,
        )
        await record_event(
            self.session,
            room.id,
            "conflict.injected",
            {
                "fact_key": payload["fact_key"],
                "fact_value": payload["fact_value"],
                "target_participant_ids": [str(p.id) for p in recipients],
            },
            actor_id=actor_id,
            actor_type=ActorType.USER,
            sim_time=sim,
        )
        await self.delivery.create_message(room, spec, recipients, sim, actor_id=actor_id)

    # --------------------------------------------------------------- channels

    async def _channel_by_key(self, room: SimulationRoom, key: str | None) -> CommunicationChannel:
        for c in await self.channels(room):
            if c.key == key:
                return c
        raise not_found("CHANNEL_NOT_FOUND", f"Channel '{key}' not found.")

    async def set_channel_state(
        self,
        room: SimulationRoom,
        channel: CommunicationChannel,
        *,
        status: str,
        reliability: float | None,
        latency_ms: int | None,
        reason: str,
        actor_id: uuid.UUID | None,
        sim: float,
    ) -> None:
        previous = {
            "status": channel.status,
            "reliability": channel.reliability,
            "latency_ms": channel.latency_ms,
        }
        channel.status = ChannelStatus(status).value
        if reliability is not None:
            channel.reliability = max(0.0, min(1.0, float(reliability)))
        if latency_ms is not None:
            channel.latency_ms = max(0, int(latency_ms))
        self.session.add(
            ChannelStateChange(
                room_id=room.id,
                channel_id=channel.id,
                sim_time=sim,
                status=channel.status,
                reliability=channel.reliability,
                latency_ms=channel.latency_ms,
                reason=reason[:200],
                actor_id=actor_id,
            )
        )
        await record_event(
            self.session,
            room.id,
            "channel.updated",
            {
                "channel_id": str(channel.id),
                "key": channel.key,
                "name": channel.name,
                "status": channel.status,
                "reliability": channel.reliability,
                "latency_ms": channel.latency_ms,
                "previous": previous,
                "reason": reason,
            },
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.ENGINE,
            sim_time=sim,
            visibility=EventVisibility.ALL,
        )

    async def update_channel(
        self,
        room: SimulationRoom,
        channel_id: uuid.UUID,
        changes: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> CommunicationChannel:
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        channel = next((c for c in await self.channels(room) if c.id == channel_id), None)
        if channel is None:
            raise not_found("CHANNEL_NOT_FOUND", "Channel not found.")
        status = changes.get("status") or channel.status
        reliability = changes.get("reliability")
        latency = changes.get("latency_ms")
        if changes.get("restore"):
            initial = next(
                (c for c in self.snapshot(room).get("channels", []) if c["key"] == channel.key),
                None,
            )
            status = ChannelStatus.ONLINE.value
            reliability = initial["reliability"] if initial else 0.95
            latency = initial["latency_ms"] if initial else 500
        sim = self.now_sim(room)
        await self.set_channel_state(
            room,
            channel,
            status=status,
            reliability=reliability,
            latency_ms=latency,
            reason=changes.get("reason") or "Instructor adjustment",
            actor_id=actor_id,
            sim=sim,
        )
        await self.delivery.release_held(room, sim)
        return channel

    # ------------------------------------------------------------ disruptions

    async def create_disruption(
        self,
        room: SimulationRoom,
        *,
        disruption_type: str,
        target_participant_ids: list[str],
        target_channel_ids: list[str],
        severity: int,
        config: dict[str, Any],
        duration_seconds: float | None,
        actor_id: uuid.UUID | None,
        sim: float,
        source: str = "INSTRUCTOR",
    ) -> CommunicationDisruption:
        dtype = DisruptionType(disruption_type)
        participants = await self.participants(room)
        channels = await self.channels(room)
        valid_p = {str(p.id) for p in participants}
        valid_c = {str(c.id): c for c in channels}
        if not set(target_participant_ids) <= valid_p:
            raise AppError("INVALID_TARGET", "Unknown participant in disruption targets.", 422)
        if not set(target_channel_ids) <= set(valid_c):
            raise AppError("INVALID_TARGET", "Unknown channel in disruption targets.", 422)
        if dtype == DisruptionType.CHANNEL_FAILURE and not target_channel_ids:
            raise AppError("INVALID_TARGET", "Channel failure needs at least one channel.", 422)

        disruption = CommunicationDisruption(
            room_id=room.id,
            created_by=actor_id,
            disruption_type=dtype.value,
            target_participant_ids=target_participant_ids,
            target_channel_ids=target_channel_ids,
            severity=severity,
            start_sim_time=sim,
            planned_end_sim_time=(sim + float(duration_seconds)) if duration_seconds else None,
            configuration=dict(config),
            is_active=True,
            source=source,
        )
        self.session.add(disruption)
        await self.session.flush()

        # Global effects are applied to channel state so everyone sees them.
        affected_channels = [valid_c[cid] for cid in target_channel_ids] or (
            channels
            if dtype == DisruptionType.RELIABILITY_REDUCTION and not target_participant_ids
            else []
        )
        if dtype == DisruptionType.CHANNEL_FAILURE:
            disruption.configuration = {
                **disruption.configuration,
                "previous": {str(c.id): {"status": c.status} for c in affected_channels},
            }
            for c in affected_channels:
                await self.set_channel_state(
                    room,
                    c,
                    status=ChannelStatus.OFFLINE.value,
                    reliability=None,
                    latency_ms=None,
                    reason="Channel failure disruption",
                    actor_id=actor_id,
                    sim=sim,
                )
        elif dtype == DisruptionType.RELIABILITY_REDUCTION and not target_participant_ids:
            factor = float(config.get("factor", 0.5))
            disruption.configuration = {
                **disruption.configuration,
                "factor": factor,
                "global": True,
                "previous": {
                    str(c.id): {"status": c.status, "reliability": c.reliability}
                    for c in affected_channels
                },
            }
            for c in affected_channels:
                new_rel = round(c.reliability * factor, 3)
                status = (
                    c.status
                    if c.status == ChannelStatus.OFFLINE
                    else (ChannelStatus.DEGRADED.value if new_rel < 0.8 else c.status)
                )
                await self.set_channel_state(
                    room,
                    c,
                    status=status,
                    reliability=new_rel,
                    latency_ms=None,
                    reason="Reliability reduction disruption",
                    actor_id=actor_id,
                    sim=sim,
                )

        await record_event(
            self.session,
            room.id,
            "disruption.started",
            {
                "disruption_id": str(disruption.id),
                "disruption_type": dtype.value,
                "target_participant_ids": target_participant_ids,
                "target_channel_ids": target_channel_ids,
                "severity": severity,
                "configuration": disruption.configuration,
                "planned_end_sim_time": disruption.planned_end_sim_time,
                "source": source,
            },
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.ENGINE,
            sim_time=sim,
        )
        if dtype == DisruptionType.BLACKOUT:
            await record_event(
                self.session,
                room.id,
                "comms.changed",
                {"reason": "blackout"},
                actor_type=ActorType.ENGINE,
                sim_time=sim,
                visibility=EventVisibility.PARTICIPANTS,
                targets=target_participant_ids or [str(p.id) for p in participants],
            )
        return disruption

    async def end_disruption(
        self,
        room: SimulationRoom,
        disruption: CommunicationDisruption,
        actor_id: uuid.UUID | None,
        sim: float,
        reason: str = "Ended by instructor",
    ) -> None:
        if not disruption.is_active:
            raise conflict("DISRUPTION_NOT_ACTIVE", "Disruption already ended.")
        disruption.is_active = False
        disruption.end_sim_time = sim
        disruption.end_time = self.clock.now()
        channels = {str(c.id): c for c in await self.channels(room)}
        previous = (disruption.configuration or {}).get("previous", {})
        if disruption.disruption_type in (
            DisruptionType.CHANNEL_FAILURE,
            DisruptionType.RELIABILITY_REDUCTION,
        ):
            for cid, prev in previous.items():
                c = channels.get(cid)
                if c is None:
                    continue
                await self.set_channel_state(
                    room,
                    c,
                    status=prev.get("status", ChannelStatus.ONLINE.value),
                    reliability=prev.get("reliability"),
                    latency_ms=None,
                    reason=f"Disruption ended: {reason}",
                    actor_id=actor_id,
                    sim=sim,
                )
        await record_event(
            self.session,
            room.id,
            "disruption.ended",
            {
                "disruption_id": str(disruption.id),
                "disruption_type": disruption.disruption_type,
                "reason": reason,
            },
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.ENGINE,
            sim_time=sim,
        )
        if disruption.disruption_type == DisruptionType.BLACKOUT:
            participants = await self.participants(room)
            await record_event(
                self.session,
                room.id,
                "comms.changed",
                {"reason": "blackout ended"},
                actor_type=ActorType.ENGINE,
                sim_time=sim,
                visibility=EventVisibility.PARTICIPANTS,
                targets=disruption.target_participant_ids or [str(p.id) for p in participants],
            )
        if room.status in (RoomStatus.RUNNING, RoomStatus.PAUSED):
            await self.delivery.release_held(room, sim)

    # --------------------------------------------------------- decision points

    async def _decision_points(self, room: SimulationRoom) -> list[RoomDecisionPoint]:
        result = await self.session.scalars(
            select(RoomDecisionPoint)
            .where(RoomDecisionPoint.room_id == room.id)
            .order_by(RoomDecisionPoint.opened_sim_time)
        )
        return list(result.all())

    def decision_template(self, room: SimulationRoom, key: str) -> dict[str, Any]:
        for dp in self.snapshot(room).get("decision_points", []):
            if dp["key"] == key:
                return dict(dp)
        raise not_found("DECISION_POINT_NOT_FOUND", f"Decision point '{key}' not found.")

    async def open_decision_point(
        self, room: SimulationRoom, tmpl: dict[str, Any], sim: float, *, actor_id: uuid.UUID | None
    ) -> RoomDecisionPoint:
        participants = await self.participants(room)
        targets = self.resolve_recipients(participants, tmpl.get("target_roles") or "all")
        dp = RoomDecisionPoint(
            room_id=room.id,
            key=tmpl["key"],
            title=tmpl["title"],
            prompt=tmpl["prompt"],
            options=tmpl.get("options", []),
            allow_custom=bool(tmpl.get("allow_custom")),
            require_rationale=bool(tmpl.get("require_rationale", True)),
            target_participant_ids=[str(p.id) for p in targets],
            relevant_fact_keys=tmpl.get("relevant_fact_keys", []),
            critical=bool(tmpl.get("critical")),
            status=DecisionPointStatus.OPEN.value,
            opened_sim_time=sim,
            deadline_sim_time=sim + float(tmpl.get("deadline_seconds", 120)),
            triggered_by=actor_id,
        )
        self.session.add(dp)
        await self.session.flush()
        await record_event(
            self.session,
            room.id,
            "decision.requested",
            trainee_decision_point(dp),
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.ENGINE,
            sim_time=sim,
            visibility=EventVisibility.PARTICIPANTS,
            targets=dp.target_participant_ids,
        )
        return dp

    async def open_decision_point_now(
        self, room: SimulationRoom, key: str, actor_id: uuid.UUID
    ) -> RoomDecisionPoint:
        self._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
        tmpl = self.decision_template(room, key)
        existing = await self.session.scalar(
            select(RoomDecisionPoint).where(
                RoomDecisionPoint.room_id == room.id, RoomDecisionPoint.key == key
            )
        )
        if existing is not None:
            raise conflict(
                "DECISION_POINT_ALREADY_OPENED", "This decision point has already been opened."
            )
        return await self.open_decision_point(room, tmpl, self.now_sim(room), actor_id=actor_id)

    async def _close_decision_point(
        self, room: SimulationRoom, dp: RoomDecisionPoint, sim: float, reason: str
    ) -> None:
        dp.status = DecisionPointStatus.CLOSED.value
        dp.closed_sim_time = sim
        submitted = set(
            str(pid)
            for pid in (
                await self.session.scalars(
                    select(Decision.participant_id).where(Decision.decision_point_id == dp.id)
                )
            ).all()
        )
        missing = [pid for pid in dp.target_participant_ids if pid not in submitted]
        await record_event(
            self.session,
            room.id,
            "decision.closed",
            {"decision_point_id": str(dp.id), "key": dp.key, "title": dp.title, "reason": reason},
            actor_type=ActorType.ENGINE,
            sim_time=sim,
            visibility=EventVisibility.ALL,
        )
        if missing:
            await record_event(
                self.session,
                room.id,
                "decision.missed",
                {"decision_point_id": str(dp.id), "key": dp.key, "participant_ids": missing},
                actor_type=ActorType.ENGINE,
                sim_time=sim,
            )

    async def close_if_complete(
        self, room: SimulationRoom, dp: RoomDecisionPoint, sim: float
    ) -> bool:
        count = len(
            (
                await self.session.scalars(
                    select(Decision.id).where(Decision.decision_point_id == dp.id)
                )
            ).all()
        )
        if dp.status == DecisionPointStatus.OPEN and count >= len(dp.target_participant_ids):
            await self._close_decision_point(room, dp, sim, reason="All responses received")
            return True
        return False

    # ----------------------------------------------------------------- metrics

    async def _metric_snapshot(self, room: SimulationRoom, sim: float) -> None:
        room.last_metrics_sim_time = sim
        participants = await self.participants(room)
        if not participants:
            return
        service = InformationStateService(self.session)
        rows = []
        for p in participants:
            state = await service.reconstruct(room, p.id, sim)
            mt = state["metrics"]
            snapshot = MetricSnapshot(
                room_id=room.id,
                participant_id=p.id,
                sim_time=sim,
                communication_health=mt["communication_health"],
                information_completeness=mt["information_completeness"],
                information_reliability=mt["information_reliability"],
                uncertainty_index=mt["uncertainty_index"],
            )
            self.session.add(snapshot)
            rows.append(
                {
                    "participant_id": str(p.id),
                    "callsign": p.callsign,
                    **{k: v for k, v in mt.items() if k != "counts"},
                }
            )
        team = MetricSnapshot(
            room_id=room.id,
            participant_id=None,
            sim_time=sim,
            communication_health=m.mean(r["communication_health"] for r in rows),
            information_completeness=m.mean(r["information_completeness"] for r in rows),
            information_reliability=m.mean(r["information_reliability"] for r in rows),
            uncertainty_index=m.mean(r["uncertainty_index"] for r in rows),
        )
        self.session.add(team)
        await record_event(
            self.session,
            room.id,
            "metrics.updated",
            {"participants": rows},
            actor_type=ActorType.ENGINE,
            sim_time=sim,
        )
