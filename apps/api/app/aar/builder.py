"""After Action Review builder.

Builds the AAR purely from recorded history (decisions + their frozen information
snapshots, deliveries, disruptions, channel history, notes). All scores are explainable
EXPERIMENTAL TRAINING METRICS - each comes with the formula used to compute it.
"""

import uuid
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.models.audit import AuditEvent
from app.models.decision import Decision, InformationSnapshot
from app.models.enums import DeliveryStatus
from app.models.messaging import CommunicationDisruption, Message, MessageDelivery, TeamMessage
from app.models.room import (
    ChannelStateChange,
    CommunicationChannel,
    InstructorNote,
    Participant,
    RoomDecisionPoint,
    SimulationRoom,
)
from app.models.user import User
from app.scenario.clock import format_sim_time
from app.services import metrics as m
from app.services.information_state import InformationStateService

FORMULAS = {
    "information_confidence": "0.40 x Completeness + 0.30 x Reliability + 0.30 x Comm Health - min(30, 10 x contradictions)",
    "uncertainty_index": "100 - Information Confidence",
    "decision_response_score": "mean over assigned decisions of 100 x (1 - 0.5 x response_time / window); missed = 0",
    "information_awareness": "0.7 x mean completeness at decision time + 0.3 x acknowledgement rate",
    "decision_quality": "mean scenario-designer rubric score (truth_alignment) of selected options; custom = 50",
    "uncertainty_management": "mean of 100 - |confidence - information confidence at decision| (calibration)",
    "coordination_score": "0.4 x decision agreement + 0.3 x communication participation + 0.3 x acknowledgement rate",
}


def _option(dp: RoomDecisionPoint, key: str | None) -> dict[str, Any] | None:
    return next((o for o in dp.options if o["key"] == key), None) if key else None


async def _load(session: AsyncSession, room: SimulationRoom) -> dict[str, Any]:
    async def all_(stmt: Any) -> list[Any]:
        return list((await session.scalars(stmt)).all())

    rid = room.id
    participants = await all_(
        select(Participant).where(Participant.room_id == rid).order_by(Participant.joined_at)
    )
    users = {
        u.id: u
        for u in await all_(
            select(User).where(User.id.in_([p.user_id for p in participants] or [uuid.uuid4()]))
        )
    }
    return {
        "participants": participants,
        "users": users,
        "points": await all_(
            select(RoomDecisionPoint)
            .where(RoomDecisionPoint.room_id == rid)
            .order_by(RoomDecisionPoint.opened_sim_time)
        ),
        "decisions": await all_(
            select(Decision).where(Decision.room_id == rid).order_by(Decision.submitted_sim_time)
        ),
        "snapshots": await all_(
            select(InformationSnapshot).where(InformationSnapshot.room_id == rid)
        ),
        "messages": await all_(
            select(Message).where(Message.room_id == rid).order_by(Message.created_sim_time)
        ),
        "deliveries": await all_(select(MessageDelivery).where(MessageDelivery.room_id == rid)),
        "disruptions": await all_(
            select(CommunicationDisruption)
            .where(CommunicationDisruption.room_id == rid)
            .order_by(CommunicationDisruption.start_sim_time)
        ),
        "channels": await all_(
            select(CommunicationChannel)
            .where(CommunicationChannel.room_id == rid)
            .order_by(CommunicationChannel.sort_order)
        ),
        "changes": await all_(
            select(ChannelStateChange)
            .where(ChannelStateChange.room_id == rid)
            .order_by(ChannelStateChange.sim_time)
        ),
        "team_messages": await all_(select(TeamMessage).where(TeamMessage.room_id == rid)),
        "notes": await all_(
            select(InstructorNote)
            .where(InstructorNote.room_id == rid)
            .order_by(InstructorNote.sim_time)
        ),
        "event_counts": Counter(
            (
                await session.scalars(
                    select(AuditEvent.event_type).where(AuditEvent.room_id == rid)
                )
            ).all()
        ),
    }


def _decision_record(
    d: Decision, dp: RoomDecisionPoint, snap: InformationSnapshot | None, callsign: str
) -> dict[str, Any]:
    option = _option(dp, d.selected_option)
    quality = float(option["truth_alignment"]) if option and "truth_alignment" in option else 50.0
    payload = snap.snapshot_payload if snap else {}
    metrics = payload.get("metrics", {})
    confidence_score = metrics.get("information_confidence", 50.0)
    window = (dp.deadline_sim_time - dp.opened_sim_time) if dp.deadline_sim_time else 120.0
    relevant = set(dp.relevant_fact_keys or [])
    beliefs = [b for b in payload.get("beliefs", []) if b["fact_key"] in relevant]
    missing_relevant = [
        {
            "label": i["label"],
            "title": i["title"],
            "fact_key": i.get("fact_key"),
            "state": "DROPPED"
            if i in payload.get("dropped", [])
            else i.get("eventual_outcome", "NOT_ADDRESSED"),
        }
        for i in payload.get("dropped", [])
        + payload.get("pending", [])
        + payload.get("not_addressed", [])
        if i.get("fact_key") in relevant
    ]
    return {
        "id": str(d.id),
        "participant_id": str(d.participant_id),
        "callsign": callsign,
        "decision_point_key": dp.key,
        "decision_point_title": dp.title,
        "critical": dp.critical,
        "selected_option": d.selected_option,
        "selected_label": option["label"] if option else None,
        "decision_type": d.decision_type,
        "decision_text": d.decision_text,
        "rationale": d.rationale,
        "confidence": d.confidence,
        "submitted_sim_time": d.submitted_sim_time,
        "submitted_label": format_sim_time(d.submitted_sim_time),
        "response_time_ms": d.response_time_ms,
        "decision_quality": quality,
        "custom_needs_review": option is None,
        "response_score": m.response_score(d.response_time_ms / 1000.0, window),
        "information_completeness": metrics.get("information_completeness"),
        "information_reliability": metrics.get("information_reliability"),
        "communication_health": metrics.get("communication_health"),
        "known_contradictions": metrics.get("known_contradictions", 0),
        "information_confidence": confidence_score,
        "uncertainty_index": metrics.get("uncertainty_index"),
        "calibration": m.calibration_score(d.confidence, confidence_score),
        "relevant_beliefs": beliefs,
        "missing_relevant": missing_relevant,
        "contradictions": payload.get("contradictions", []),
    }


async def build_report(session: AsyncSession, room: SimulationRoom) -> dict[str, Any]:  # noqa: C901
    data = await _load(session, room)
    snap = room.scenario_snapshot or {}
    cfg = m.DEFAULT_CONFIG
    participants: list[Participant] = data["participants"]
    callsign = {p.id: p.callsign for p in participants}
    points: dict[uuid.UUID, RoomDecisionPoint] = {dp.id: dp for dp in data["points"]}
    snap_by_decision = {s.decision_id: s for s in data["snapshots"] if s.decision_id}

    decisions = [
        _decision_record(
            d,
            points[d.decision_point_id],
            snap_by_decision.get(d.id),
            callsign.get(d.participant_id, "?"),
        )
        for d in data["decisions"]
        if d.decision_point_id in points
    ]

    # Decision agreement on shared decision points (modal choice).
    by_point: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in decisions:
        by_point[rec["decision_point_key"]].append(rec)
    modal: dict[str, str | None] = {}
    agreement_rates = []
    for key, recs in by_point.items():
        choices = Counter(r["selected_option"] or f"custom:{r['id']}" for r in recs)
        top, count = choices.most_common(1)[0]
        modal[key] = top if len(recs) > 1 else None
        if len(recs) > 1:
            agreement_rates.append(100.0 * count / len(recs))
    team_agreement = m.mean(agreement_rates, default=100.0)

    deliveries_by_p: dict[uuid.UUID, list[MessageDelivery]] = defaultdict(list)
    for d in data["deliveries"]:
        deliveries_by_p[d.participant_id].append(d)
    sent_by_p = Counter(
        t.sender_participant_id for t in data["team_messages"] if t.delivery_status == "DELIVERED"
    )
    final_sim = room.final_sim_seconds or 0.0

    participant_reports: list[dict[str, Any]] = []
    for p in participants:
        my = [r for r in decisions if r["participant_id"] == str(p.id)]
        assigned = [dp for dp in data["points"] if str(p.id) in dp.target_participant_ids]
        missed = [dp.key for dp in assigned if dp.key not in {r["decision_point_key"] for r in my}]
        response_scores = [r["response_score"] for r in my] + [0.0] * len(missed)
        dels = deliveries_by_p.get(p.id, [])
        received = [
            d
            for d in dels
            if d.delivery_status in (DeliveryStatus.DELIVERED, DeliveryStatus.ALTERED)
        ]
        acked = [d for d in received if d.acknowledged_sim_time is not None]
        ack_rate = (len(acked) / len(received)) if received else 0.0
        completeness_at_decisions = [
            r["information_completeness"] for r in my if r["information_completeness"] is not None
        ]
        awareness = 0.7 * m.mean(completeness_at_decisions, default=0.0) + 30.0 * ack_rate
        shared = [r for r in my if modal.get(r["decision_point_key"])]
        agreement = (
            100.0
            * sum(
                1
                for r in shared
                if (r["selected_option"] or f"custom:{r['id']}") == modal[r["decision_point_key"]]
            )
            / len(shared)
            if shared
            else 100.0
        )
        participation = min(1.0, sent_by_p.get(p.id, 0) / 3.0) * 100.0
        coordination = 0.4 * agreement + 0.3 * participation + 0.3 * ack_rate * 100.0
        quality = m.mean((r["decision_quality"] for r in my), default=0.0)
        calibration = m.mean((r["calibration"] for r in my), default=0.0)
        response = m.mean(response_scores, default=0.0)
        overall = m.mean([response, awareness, quality, coordination, calibration])
        delayed = [d for d in received if d.delay_seconds >= 5]
        contradictions_seen = max((r["known_contradictions"] for r in my), default=0)
        participant_reports.append(
            {
                "participant_id": str(p.id),
                "callsign": p.callsign,
                "display_name": data["users"][p.user_id].display_name
                if p.user_id in data["users"]
                else p.callsign,
                "role": p.assigned_role,
                "decision_response_score": round(response, 1),
                "information_awareness": round(m.clamp(awareness), 1),
                "decision_quality": round(quality, 1),
                "coordination_score": round(m.clamp(coordination), 1),
                "uncertainty_management": round(calibration, 1),
                "average_confidence": m.mean((r["confidence"] for r in my), default=0.0),
                "average_response_time_s": m.mean(
                    (r["response_time_ms"] / 1000.0 for r in my), default=0.0
                ),
                "decisions_under_high_uncertainty": sum(
                    1 for r in my if (r["uncertainty_index"] or 0) >= cfg.high_uncertainty_threshold
                ),
                "decisions_made": len(my),
                "decisions_missed": missed,
                "overall_score": round(overall, 1),
                "contradictions_encountered": contradictions_seen,
                "acknowledgement_rate": round(ack_rate * 100.0, 1),
                "team_messages_sent": sent_by_p.get(p.id, 0),
                "messages": {
                    "addressed": len(dels),
                    "received": len(received),
                    "altered": sum(
                        1 for d in received if d.delivery_status == DeliveryStatus.ALTERED
                    ),
                    "delayed": len(delayed),
                    "dropped": sum(1 for d in dels if d.delivery_status == DeliveryStatus.DROPPED),
                    "never_delivered": sum(
                        1 for d in dels if d.delivery_status == DeliveryStatus.FAILED
                    ),
                    "average_delay_s": m.mean((d.delay_seconds for d in delayed), default=0.0),
                },
            }
        )

    team_score = m.mean((p["overall_score"] for p in participant_reports), default=0.0)

    # Communication disruptions & channel history.
    channel_name = {c.id: c.name for c in data["channels"]}
    disruptions = [
        {
            "id": str(d.id),
            "disruption_type": d.disruption_type,
            "source": d.source,
            "severity": d.severity,
            "start_sim_time": d.start_sim_time,
            "end_sim_time": d.end_sim_time,
            "targets": [callsign.get(uuid.UUID(t), t) for t in d.target_participant_ids]
            or ["All participants"],
            "channels": [channel_name.get(uuid.UUID(c), c) for c in d.target_channel_ids],
            "configuration": {k: v for k, v in (d.configuration or {}).items() if k != "previous"},
        }
        for d in data["disruptions"]
    ]
    channel_history = [
        {
            "channel": channel_name.get(c.channel_id, "?"),
            "sim_time": c.sim_time,
            "status": c.status,
            "reliability": c.reliability,
            "latency_ms": c.latency_ms,
            "reason": c.reason,
        }
        for c in data["changes"]
    ]

    # Information outcomes per message (what happened to each piece of information).
    by_message: dict[uuid.UUID, list[MessageDelivery]] = defaultdict(list)
    for d in data["deliveries"]:
        by_message[d.message_id].append(d)
    information_outcomes = []
    for msg in data["messages"]:
        outcomes = []
        for d in sorted(
            by_message.get(msg.id, []), key=lambda x: callsign.get(x.participant_id, "")
        ):
            outcomes.append(
                {
                    "callsign": callsign.get(d.participant_id, "?"),
                    "status": d.delivery_status,
                    "delay_seconds": d.delay_seconds,
                    "transformation_type": d.transformation_type,
                    "delivered_fact_value": d.delivered_fact_value,
                    "reasons": (d.transformation_metadata or {}).get("reasons", []),
                }
            )
        information_outcomes.append(
            {
                "label": msg.label,
                "title": msg.title,
                "created_sim_time": msg.created_sim_time,
                "fact_key": msg.fact_key,
                "fact_value": msg.fact_value,
                "importance_weight": msg.importance_weight,
                "outcomes": outcomes,
                "narrative": [
                    f"{msg.label} was {o['status'].lower()} for {o['callsign']}"
                    + (
                        f" (+{o['delay_seconds']:.0f}s)"
                        if o["status"] in ("DELIVERED", "ALTERED") and o["delay_seconds"] >= 5
                        else ""
                    )
                    for o in outcomes
                    if o["status"] != "DELIVERED" or o["delay_seconds"] >= 5
                ],
            }
        )

    critical = [r for r in decisions if r["critical"]]
    objectives = _objective_observations(
        snap.get("objectives", []), participant_reports, decisions, team_agreement
    )
    recommendations = _recommendations(participant_reports, decisions, team_agreement)

    status_counts = Counter(d.delivery_status for d in data["deliveries"])
    duration = final_sim
    summary = (
        f"{room.name}: {len(participants)} participants, {len(decisions)} decisions over "
        f"{format_sim_time(duration)}. {status_counts.get('DROPPED', 0)} deliveries were dropped, "
        f"{sum(1 for d in data['deliveries'] if d.delay_seconds >= 5)} delayed and "
        f"{status_counts.get('ALTERED', 0)} altered. Team agreement on shared decisions: {team_agreement:.0f}%. "
        f"Training team score: {team_score:.0f}/100 (experimental metric)."
    )
    return {
        "exercise": {
            "room_id": str(room.id),
            "room_code": room.room_code,
            "title": room.name,
            "scenario": snap.get("name"),
            "scenario_description": snap.get("description"),
            "difficulty": snap.get("difficulty"),
            "started_at": room.started_at.isoformat() if room.started_at else None,
            "ended_at": room.ended_at.isoformat() if room.ended_at else None,
            "duration_seconds": duration,
            "duration_label": format_sim_time(duration),
            "objectives": snap.get("objectives", []),
            "participant_count": len(participants),
        },
        "summary": summary,
        "team": {
            "team_score": team_score,
            "decision_agreement": team_agreement,
            "average_confidence": m.mean((r["confidence"] for r in decisions), default=0.0),
            "average_response_time_s": m.mean(
                (r["response_time_ms"] / 1000 for r in decisions), default=0.0
            ),
            "average_uncertainty_at_decision": m.mean(
                (r["uncertainty_index"] for r in decisions if r["uncertainty_index"] is not None),
                default=0.0,
            ),
            "average_coordination": m.mean(
                (p["coordination_score"] for p in participant_reports), default=0.0
            ),
            "delivery_status_counts": dict(status_counts),
            "messages_created": len(data["messages"]),
            "disruptions": len(disruptions),
            "team_messages": len(data["team_messages"]),
        },
        "participants": participant_reports,
        "decisions": decisions,
        "critical_decisions": critical,
        "disruptions": disruptions,
        "channel_history": channel_history,
        "information_outcomes": information_outcomes,
        "objectives": objectives,
        "recommendations": recommendations,
        "notes": [
            {
                "sim_time": n.sim_time,
                "label": format_sim_time(n.sim_time),
                "content": n.content,
                "callsign": callsign.get(n.participant_id) if n.participant_id else None,
            }
            for n in data["notes"]
        ],
        "timeline_counts": dict(data["event_counts"]),
        "formulas": FORMULAS,
        "metric_disclaimer": (
            "All scores are experimental training metrics intended to support discussion in the "
            "After Action Review. They are not scientifically validated performance measures."
        ),
    }


def _objective_observations(
    objectives: list[dict[str, Any]],
    participants: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    agreement: float,
) -> list[dict[str, Any]]:
    out = []
    for obj in objectives:
        key = obj.get("key", "")
        obs: list[str] = []
        if key == "incomplete_info":
            for p in participants:
                mine = [d for d in decisions if d["participant_id"] == p["participant_id"]]
                if mine:
                    comp = m.mean(d["information_completeness"] or 0 for d in mine)
                    obs.append(
                        f"{p['callsign']} decided with {comp:.0f}% average information completeness "
                        f"(decision quality {p['decision_quality']:.0f})."
                    )
        elif key == "contradictions":
            for d in decisions:
                if d["known_contradictions"]:
                    obs.append(
                        f"{d['callsign']} held {d['known_contradictions']} contradictory report set(s) when deciding "
                        f"'{d['decision_point_title']}' and chose '{d['selected_label'] or d['decision_text']}' "
                        f"at {d['confidence']}% confidence."
                    )
            if not obs:
                obs.append("No participant held contradictory reports at a decision point.")
        elif key == "coordination":
            obs.append(f"Team agreement on shared decisions was {agreement:.0f}%.")
            for p in participants:
                obs.append(
                    f"{p['callsign']} sent {p['team_messages_sent']} team message(s) and acknowledged "
                    f"{p['acknowledgement_rate']:.0f}% of received reports."
                )
        elif key == "calibration":
            for p in participants:
                obs.append(
                    f"{p['callsign']} confidence calibration score: {p['uncertainty_management']:.0f} "
                    f"(average confidence {p['average_confidence']:.0f}%)."
                )
        elif key == "comm_priority":
            for p in participants:
                msgs = p["messages"]
                obs.append(
                    f"{p['callsign']}: {msgs['received']}/{msgs['addressed']} reports received, "
                    f"{msgs['delayed']} delayed, {msgs['dropped']} dropped."
                )
        else:
            obs.append("Review decision timeline and participant comparison for this objective.")
        out.append({**obj, "observations": obs})
    return out


def _recommendations(
    participants: list[dict[str, Any]], decisions: list[dict[str, Any]], agreement: float
) -> list[str]:
    recs: list[str] = []
    for p in participants:
        if p["uncertainty_management"] and p["uncertainty_management"] < 65:
            recs.append(
                f"{p['callsign']}: practise confidence calibration - stated confidence diverged from "
                f"the quality of information available."
            )
        if p["acknowledgement_rate"] < 50:
            recs.append(
                f"{p['callsign']}: acknowledge incoming reports so the team knows what has been seen."
            )
        if p["decisions_missed"]:
            recs.append(
                f"{p['callsign']}: missed {len(p['decisions_missed'])} decision window(s); rehearse "
                f"time-boxed decision making."
            )
        if p["team_messages_sent"] == 0:
            recs.append(
                f"{p['callsign']}: share critical reports over working channels - no team messages were sent."
            )
    contradiction_decisions = [
        d for d in decisions if d["known_contradictions"] and d["confidence"] >= 75
    ]
    if contradiction_decisions:
        recs.append(
            "Several decisions were made at high confidence despite known contradictory reports - "
            "discuss verification strategies and source reliability weighting."
        )
    if agreement < 60:
        recs.append(
            "Low agreement on shared decisions suggests the cell did not converge on a common picture; "
            "practise structured information sharing before committing."
        )
    if not recs:
        recs.append(
            "Strong performance - increase scenario difficulty or communication degradation next time."
        )
    return recs


async def inspect_decision(
    session: AsyncSession, room: SimulationRoom, decision_id: uuid.UUID
) -> dict[str, Any]:
    """Everything the instructor needs to judge one decision in context."""
    decision = await session.get(Decision, decision_id)
    if decision is None or decision.room_id != room.id:
        raise not_found("DECISION_NOT_FOUND", "Decision not found.")
    dp = await session.get(RoomDecisionPoint, decision.decision_point_id)
    assert dp is not None
    participant = await session.get(Participant, decision.participant_id)
    snapshot = await session.scalar(
        select(InformationSnapshot).where(InformationSnapshot.decision_id == decision.id)
    )
    record = _decision_record(decision, dp, snapshot, participant.callsign if participant else "?")
    # Reconstruct from recorded history at the decision time. What was known is identical
    # to the frozen snapshot; history additionally tells us what arrived *after* the decision.
    t = snapshot.snapshot_time if snapshot else decision.submitted_sim_time
    payload = await InformationStateService(session).reconstruct(room, decision.participant_id, t)
    received = payload.get("received", [])
    return {
        "decision": record,
        "decision_point": {
            "key": dp.key,
            "title": dp.title,
            "prompt": dp.prompt,
            "options": dp.options,
            "opened_sim_time": dp.opened_sim_time,
            "deadline_sim_time": dp.deadline_sim_time,
            "relevant_fact_keys": dp.relevant_fact_keys,
        },
        "participant": {
            "id": str(decision.participant_id),
            "callsign": participant.callsign if participant else None,
            "role": participant.assigned_role if participant else None,
        },
        "snapshot_time": snapshot.snapshot_time if snapshot else decision.submitted_sim_time,
        "available_information": received,
        "missing_information": {
            "dropped": payload.get("dropped", []),
            "not_addressed": payload.get("not_addressed", []),
            "in_flight": payload.get("pending", []),
        },
        "delayed_information": {
            "arrived_late": [i for i in received if (i.get("delay_seconds") or 0) >= 5],
            "arrived_after_decision": [
                i
                for i in payload.get("pending", [])
                if i.get("eventual_outcome") == "DELIVERED_LATER"
            ],
        },
        "conflicting_information": payload.get("contradictions", []),
        "beliefs": payload.get("beliefs", []),
        "channels": payload.get("channels", []),
        "metrics": payload.get("metrics", {}),
        "truth": payload.get("truth", {}),
    }
