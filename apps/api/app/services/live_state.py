"""Read models for the live instructor console and the trainee dashboard.

The trainee read model is built ONLY from that participant's deliveries - never from the
global message table - so undelivered or dropped information cannot leak.
"""

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.decision import Decision
from app.models.enums import ChannelStatus, DeliveryStatus, DisruptionType
from app.models.messaging import (
    CommunicationDisruption,
    Message,
    MessageDelivery,
    ScenarioEvent,
    TeamMessage,
)
from app.models.room import (
    CommunicationChannel,
    InstructorNote,
    Participant,
    RoomDecisionPoint,
    SimulationRoom,
)
from app.models.user import User
from app.realtime.visibility import is_visible
from app.scenario.clock import Clock, sim_now
from app.scenario.engine import trainee_decision_point
from app.services import metrics as m
from app.services.audit import event_to_wire
from app.services.delivery import trainee_message_view
from app.services.information_state import InformationStateService

RECEIVED = (DeliveryStatus.DELIVERED.value, DeliveryStatus.ALTERED.value)


def channel_out(c: CommunicationChannel, effective_status: str | None = None) -> dict[str, Any]:
    status = effective_status or c.status
    health = 0 if status == ChannelStatus.OFFLINE else round(c.reliability * 100)
    return {
        "id": str(c.id),
        "key": c.key,
        "name": c.name,
        "channel_type": c.channel_type,
        "status": status,
        "base_status": c.status,
        "reliability": c.reliability,
        "latency_ms": c.latency_ms,
        "health": health,
        "weight": c.weight,
        "fallback_channel_key": c.fallback_channel_key,
    }


async def room_participants(
    session: AsyncSession, room_id: uuid.UUID
) -> list[tuple[Participant, User]]:
    rows = await session.execute(
        select(Participant, User)
        .join(User, User.id == Participant.user_id)
        .where(Participant.room_id == room_id)
        .order_by(Participant.joined_at)
    )
    return [(p, u) for p, u in rows.all()]


def participant_out(p: Participant, u: User, roles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    role = roles.get(p.assigned_role or "")
    return {
        "id": str(p.id),
        "user_id": str(p.user_id),
        "display_name": u.display_name,
        "callsign": p.callsign,
        "assigned_role": p.assigned_role,
        "role_name": role["name"] if role else None,
        "team": p.team,
        "connection_status": p.connection_status,
        "is_ready": p.is_ready,
        "joined_at": p.joined_at.isoformat() if p.joined_at else None,
        "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
    }


async def room_summary(session: AsyncSession, room: SimulationRoom, clock: Clock) -> dict[str, Any]:
    snap = room.scenario_snapshot or {}
    roles = {r["key"]: r for r in snap.get("roles", [])}
    instructor = await session.get(User, room.instructor_id)
    participants = await room_participants(session, room.id)
    return {
        "id": str(room.id),
        "room_code": room.room_code,
        "name": room.name,
        "status": room.status,
        "scenario_id": str(room.scenario_template_id) if room.scenario_template_id else None,
        "scenario_name": snap.get("name"),
        "scenario_description": snap.get("description"),
        "difficulty": snap.get("difficulty"),
        "estimated_duration_minutes": snap.get("estimated_duration_minutes"),
        "instructor": {"id": str(instructor.id), "display_name": instructor.display_name}
        if instructor
        else None,
        "time_scale": room.time_scale,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "ended_at": room.ended_at.isoformat() if room.ended_at else None,
        "sim_time": sim_now(room, clock.now()),
        "current_phase_key": room.current_phase_key,
        "roles": [
            {"key": r["key"], "name": r["name"], "callsign": r["callsign"]} for r in roles.values()
        ],
        "participants": [participant_out(p, u, roles) for p, u in participants],
    }


def _phase(snap: dict[str, Any], key: str | None) -> dict[str, Any] | None:
    return next((p for p in snap.get("phases", []) if p["key"] == key), None)


async def instructor_state(
    session: AsyncSession, room: SimulationRoom, clock: Clock
) -> dict[str, Any]:
    snap = room.scenario_snapshot or {}
    sim = sim_now(room, clock.now())
    summary = await room_summary(session, room, clock)

    channels = (
        await session.scalars(
            select(CommunicationChannel)
            .where(CommunicationChannel.room_id == room.id)
            .order_by(CommunicationChannel.sort_order)
        )
    ).all()
    disruptions = (
        await session.scalars(
            select(CommunicationDisruption)
            .where(CommunicationDisruption.room_id == room.id)
            .order_by(CommunicationDisruption.start_sim_time.desc())
        )
    ).all()
    counts = Counter(
        (str(pid), status)
        for pid, status in (
            await session.execute(
                select(MessageDelivery.participant_id, MessageDelivery.delivery_status).where(
                    MessageDelivery.room_id == room.id
                )
            )
        ).all()
    )

    # Live per-participant information metrics (digital twin at "now").
    service = InformationStateService(session)
    participant_rows = []
    for p in summary["participants"]:
        pid = p["id"]
        metrics_now: dict[str, Any] | None = None
        if room.status != "LOBBY":
            state = await service.reconstruct(room, uuid.UUID(pid), sim)
            metrics_now = state["metrics"]
        participant_rows.append(
            {
                **p,
                "deliveries": {
                    "received": counts[(pid, "DELIVERED")] + counts[(pid, "ALTERED")],
                    "altered": counts[(pid, "ALTERED")],
                    "in_flight": counts[(pid, "DELAYED")] + counts[(pid, "PENDING")],
                    "dropped": counts[(pid, "DROPPED")],
                    "failed": counts[(pid, "FAILED")],
                },
                "metrics": metrics_now,
            }
        )

    points = (
        await session.scalars(
            select(RoomDecisionPoint)
            .where(RoomDecisionPoint.room_id == room.id)
            .order_by(RoomDecisionPoint.opened_sim_time)
        )
    ).all()
    decisions = (
        await session.scalars(
            select(Decision)
            .where(Decision.room_id == room.id)
            .order_by(Decision.submitted_sim_time.desc())
        )
    ).all()
    callsign = {p["id"]: p["callsign"] for p in summary["participants"]}
    point_by_id = {dp.id: dp for dp in points}

    fired = {
        e.template_key: e.sim_time
        for e in (
            await session.scalars(select(ScenarioEvent).where(ScenarioEvent.room_id == room.id))
        ).all()
        if e.template_key
    }
    opened = {dp.key: dp for dp in points}
    timeline = []
    for ev in snap.get("events", []):
        timeline.append(
            {
                "kind": "EVENT",
                "key": ev["key"],
                "title": ev["title"],
                "event_type": ev["event_type"],
                "trigger_type": ev.get("trigger_type", "TIME"),
                "scheduled_sim_time": ev.get("scheduled_offset_seconds"),
                "fired_sim_time": fired.get(ev["key"]),
                "status": "FIRED" if ev["key"] in fired else "UPCOMING",
                "channel_key": ev.get("channel_key"),
                "has_variants": bool(ev.get("variants")),
            }
        )
    for dp in snap.get("decision_points", []):
        rdp = opened.get(dp["key"])
        timeline.append(
            {
                "kind": "DECISION",
                "key": dp["key"],
                "title": dp["title"],
                "trigger_type": dp.get("trigger_type", "TIME"),
                "scheduled_sim_time": dp.get("opens_at_seconds"),
                "fired_sim_time": rdp.opened_sim_time if rdp else None,
                "status": rdp.status if rdp else "UPCOMING",
            }
        )
    timeline.sort(key=lambda x: (x["scheduled_sim_time"] is None, x["scheduled_sim_time"] or 0))

    recent = (
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.room_id == room.id)
            .order_by(AuditEvent.seq.desc())
            .limit(80)
        )
    ).all()
    notes = (
        await session.scalars(
            select(InstructorNote)
            .where(InstructorNote.room_id == room.id)
            .order_by(InstructorNote.sim_time)
        )
    ).all()

    variants = [
        {
            "event_key": ev["key"],
            "fact_key": ev.get("fact_key"),
            "canonical_value": ev.get("fact_value"),
            "variant_key": v["key"],
            "variant_value": v["fact_value"],
            "content": v["content"],
        }
        for ev in snap.get("events", [])
        for v in ev.get("variants", [])
    ]
    return {
        "room": summary,
        "sim_time": sim,
        "phase": _phase(snap, room.current_phase_key),
        "phases": snap.get("phases", []),
        "channels": [channel_out(c) for c in channels],
        "participants": participant_rows,
        "disruptions": [
            {
                "id": str(d.id),
                "disruption_type": d.disruption_type,
                "target_participant_ids": d.target_participant_ids,
                "target_channel_ids": d.target_channel_ids,
                "severity": d.severity,
                "configuration": d.configuration,
                "start_sim_time": d.start_sim_time,
                "end_sim_time": d.end_sim_time,
                "planned_end_sim_time": d.planned_end_sim_time,
                "is_active": d.is_active,
                "source": d.source,
            }
            for d in disruptions
        ],
        "decision_points": [
            {
                **trainee_decision_point(dp),
                "options": dp.options,
                "target_participant_ids": dp.target_participant_ids,
                "submitted_participant_ids": [
                    str(d.participant_id) for d in decisions if d.decision_point_id == dp.id
                ],
            }
            for dp in points
        ],
        "decisions": [
            {
                "id": str(d.id),
                "participant_id": str(d.participant_id),
                "callsign": callsign.get(str(d.participant_id)),
                "decision_point_key": point_by_id[d.decision_point_id].key
                if d.decision_point_id in point_by_id
                else None,
                "decision_point_title": point_by_id[d.decision_point_id].title
                if d.decision_point_id in point_by_id
                else None,
                "selected_option": d.selected_option,
                "selected_label": next(
                    (
                        o["label"]
                        for o in (
                            point_by_id[d.decision_point_id].options
                            if d.decision_point_id in point_by_id
                            else []
                        )
                        if o["key"] == d.selected_option
                    ),
                    None,
                ),
                "decision_text": d.decision_text,
                "rationale": d.rationale,
                "confidence": d.confidence,
                "response_time_ms": d.response_time_ms,
                "submitted_sim_time": d.submitted_sim_time,
            }
            for d in decisions
        ],
        "timeline": timeline,
        "events": [event_to_wire(e) for e in recent],
        "notes": [
            {
                "id": str(n.id),
                "sim_time": n.sim_time,
                "content": n.content,
                "participant_id": str(n.participant_id) if n.participant_id else None,
            }
            for n in notes
        ],
        "variants": variants,
        "facts": snap.get("initial_conditions", {}).get("facts", []),
        "locations": snap.get("initial_conditions", {}).get("locations", []),
        "objectives": snap.get("objectives", []),
        "last_seq": room.event_seq,
    }


async def effective_channels(
    session: AsyncSession, room: SimulationRoom, participant: Participant
) -> tuple[list[dict[str, Any]], bool]:
    channels = (
        await session.scalars(
            select(CommunicationChannel)
            .where(CommunicationChannel.room_id == room.id)
            .order_by(CommunicationChannel.sort_order)
        )
    ).all()
    disruptions = (
        await session.scalars(
            select(CommunicationDisruption).where(
                CommunicationDisruption.room_id == room.id,
                CommunicationDisruption.is_active.is_(True),
                CommunicationDisruption.disruption_type == DisruptionType.BLACKOUT,
            )
        )
    ).all()
    pid = str(participant.id)
    blackout = any(
        not d.target_participant_ids or pid in d.target_participant_ids for d in disruptions
    )
    return [
        channel_out(c, ChannelStatus.OFFLINE.value if blackout else None) for c in channels
    ], blackout


async def trainee_state(
    session: AsyncSession, room: SimulationRoom, participant: Participant, clock: Clock
) -> dict[str, Any]:
    snap = room.scenario_snapshot or {}
    sim = sim_now(room, clock.now())
    roles = {r["key"]: r for r in snap.get("roles", [])}
    role = roles.get(participant.assigned_role or "")

    channels, blackout = await effective_channels(session, room, participant)
    comm_health = m.communication_health(
        m.ChannelHealthItem(c["weight"], c["status"], c["reliability"]) for c in channels
    )
    rows = (
        await session.execute(
            select(MessageDelivery, Message, CommunicationChannel)
            .join(Message, Message.id == MessageDelivery.message_id)
            .outerjoin(CommunicationChannel, CommunicationChannel.id == MessageDelivery.channel_id)
            .where(
                MessageDelivery.participant_id == participant.id,
                MessageDelivery.delivery_status.in_(RECEIVED),
                MessageDelivery.actual_delivery_sim_time.is_not(None),
            )
            .order_by(MessageDelivery.actual_delivery_sim_time.desc())
        )
    ).all()
    messages = [trainee_message_view(d, msg, ch) for d, msg, ch in rows]

    points = (
        await session.scalars(
            select(RoomDecisionPoint)
            .where(RoomDecisionPoint.room_id == room.id)
            .order_by(RoomDecisionPoint.opened_sim_time)
        )
    ).all()
    my_points = [dp for dp in points if str(participant.id) in dp.target_participant_ids]
    my_decisions = (
        await session.scalars(select(Decision).where(Decision.participant_id == participant.id))
    ).all()
    by_point = {d.decision_point_id: d for d in my_decisions}

    team_rows = (
        await session.scalars(
            select(TeamMessage).where(TeamMessage.room_id == room.id).order_by(TeamMessage.sim_time)
        )
    ).all()
    team_participants = await room_participants(session, room.id)
    callsign = {str(p.id): p.callsign for p, _ in team_participants}
    pid = str(participant.id)
    team_messages = [
        {
            "id": str(t.id),
            "sender_participant_id": str(t.sender_participant_id),
            "sender_callsign": callsign.get(str(t.sender_participant_id)),
            "recipient_participant_id": str(t.recipient_participant_id)
            if t.recipient_participant_id
            else None,
            "recipient_callsign": callsign.get(str(t.recipient_participant_id))
            if t.recipient_participant_id
            else None,
            "message": t.message,
            "sim_time": t.sim_time,
            "delivery_status": t.delivery_status
            if str(t.sender_participant_id) == pid
            else "DELIVERED",
            "failure_reason": t.failure_reason if str(t.sender_participant_id) == pid else None,
            "channel_key": next((c["key"] for c in channels if c["id"] == str(t.channel_id)), None),
        }
        for t in team_rows
        if str(t.sender_participant_id) == pid or pid in (t.delivered_to or [])
    ]

    visible_events = (
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.room_id == room.id)
            .order_by(AuditEvent.seq.desc())
            .limit(300)
        )
    ).all()
    notices = [
        event_to_wire(e)
        for e in visible_events
        if e.event_type
        in (
            "phase.changed",
            "channel.updated",
            "simulation.started",
            "simulation.paused",
            "simulation.resumed",
            "simulation.completed",
            "decision.closed",
        )
        and is_visible(
            e.visibility, e.target_participant_ids, is_instructor=False, participant_id=pid
        )
    ][:30]

    return {
        "room": {
            "id": str(room.id),
            "room_code": room.room_code,
            "name": room.name,
            "status": room.status,
            "scenario_name": snap.get("name"),
            "time_scale": room.time_scale,
            "sim_time": sim,
            "phase": _phase(snap, room.current_phase_key),
        },
        "participant": {
            "id": pid,
            "callsign": participant.callsign,
            "assigned_role": participant.assigned_role,
            "role_name": role["name"] if role else None,
            "role_description": role.get("description") if role else None,
            "role_objectives": role.get("objectives", []) if role else [],
            "team": participant.team,
        },
        "briefing": snap.get("briefing", ""),
        "objectives": snap.get("objectives", []),
        "locations": snap.get("initial_conditions", {}).get("locations", []),
        "map": snap.get("initial_conditions", {}).get("map", {}),
        "channels": channels,
        "blackout": blackout,
        "communication_health": comm_health,
        "messages": messages,
        "decision_points": [
            {
                **trainee_decision_point(dp),
                "my_decision": (
                    {
                        "id": str(by_point[dp.id].id),
                        "selected_option": by_point[dp.id].selected_option,
                        "decision_text": by_point[dp.id].decision_text,
                        "rationale": by_point[dp.id].rationale,
                        "confidence": by_point[dp.id].confidence,
                        "submitted_sim_time": by_point[dp.id].submitted_sim_time,
                        "response_time_ms": by_point[dp.id].response_time_ms,
                    }
                    if dp.id in by_point
                    else None
                ),
            }
            for dp in my_points
        ],
        "teammates": [
            {
                "id": str(p.id),
                "callsign": p.callsign,
                "role_name": roles.get(p.assigned_role or "", {}).get("name"),
                "connection_status": p.connection_status,
            }
            for p, _ in team_participants
            if p.id != participant.id
        ],
        "team_messages": team_messages,
        "notices": notices,
        "last_seq": room.event_seq,
    }
