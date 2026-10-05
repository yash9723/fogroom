"""Cross-exercise analytics and the instructor dashboard."""

import uuid
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aar import AARReport, MetricSnapshot
from app.models.decision import Decision, InformationSnapshot
from app.models.enums import RoomStatus, UserRole
from app.models.messaging import CommunicationDisruption, MessageDelivery
from app.models.room import Participant, SimulationRoom
from app.models.user import User
from app.services import metrics as m


async def _rooms_for(session: AsyncSession, user: User) -> list[SimulationRoom]:
    query = select(SimulationRoom).order_by(SimulationRoom.created_at.desc())
    if user.role != UserRole.ADMIN:
        query = query.where(SimulationRoom.instructor_id == user.id)
    return list((await session.scalars(query)).all())


async def dashboard(session: AsyncSession, user: User) -> dict[str, Any]:
    rooms = await _rooms_for(session, user)
    ids = [r.id for r in rooms] or [uuid.uuid4()]
    reports = list(
        (
            await session.scalars(
                select(AARReport)
                .where(AARReport.room_id.in_(ids))
                .order_by(AARReport.generated_at.desc())
            )
        ).all()
    )
    room_by_id = {r.id: r for r in rooms}
    recent_participants = (
        await session.execute(
            select(Participant, User)
            .join(User, User.id == Participant.user_id)
            .where(Participant.room_id.in_(ids))
            .order_by(Participant.joined_at.desc())
            .limit(30)
        )
    ).all()
    seen: set[uuid.UUID] = set()
    people = []
    for p, u in recent_participants:
        if u.id in seen:
            continue
        seen.add(u.id)
        people.append(
            {
                "user_id": str(u.id),
                "display_name": u.display_name,
                "callsign": p.callsign,
                "room_name": room_by_id[p.room_id].name,
                "joined_at": p.joined_at.isoformat(),
            }
        )

    def brief(r: SimulationRoom) -> dict[str, Any]:
        return {
            "id": str(r.id),
            "room_code": r.room_code,
            "name": r.name,
            "status": r.status,
            "scenario_name": (r.scenario_snapshot or {}).get("name"),
            "created_at": r.created_at.isoformat(),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        }

    return {
        "active": [brief(r) for r in rooms if r.status in (RoomStatus.RUNNING, RoomStatus.PAUSED)],
        "scheduled": [brief(r) for r in rooms if r.status == RoomStatus.LOBBY],
        "completed": [
            brief(r) for r in rooms if r.status in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED)
        ][:20],
        "recent_reports": [
            {
                "room_id": str(a.room_id),
                "room_name": room_by_id[a.room_id].name if a.room_id in room_by_id else "",
                "generated_at": a.generated_at.isoformat(),
                "team_score": a.team_score,
                "summary": a.summary,
            }
            for a in reports[:8]
        ],
        "average_team_score": m.mean((a.team_score for a in reports), default=0.0)
        if reports
        else None,
        "recent_participants": people[:10],
        "counts": {
            "total": len(rooms),
            "active": sum(1 for r in rooms if r.status in (RoomStatus.RUNNING, RoomStatus.PAUSED)),
            "completed": sum(
                1 for r in rooms if r.status in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED)
            ),
            "reports": len(reports),
        },
    }


async def overview(session: AsyncSession, user: User) -> dict[str, Any]:
    rooms = [
        r
        for r in await _rooms_for(session, user)
        if r.status in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED)
    ]
    ids = [r.id for r in rooms] or [uuid.uuid4()]
    decisions = list(
        (await session.scalars(select(Decision).where(Decision.room_id.in_(ids)))).all()
    )
    snapshots = list(
        (
            await session.scalars(
                select(InformationSnapshot).where(InformationSnapshot.room_id.in_(ids))
            )
        ).all()
    )
    reports = {
        a.room_id: a
        for a in (await session.scalars(select(AARReport).where(AARReport.room_id.in_(ids)))).all()
    }
    disruptions = list(
        (
            await session.scalars(
                select(CommunicationDisruption).where(CommunicationDisruption.room_id.in_(ids))
            )
        ).all()
    )
    statuses = Counter(
        (
            await session.scalars(
                select(MessageDelivery.delivery_status).where(MessageDelivery.room_id.in_(ids))
            )
        ).all()
    )
    participants = (
        await session.execute(
            select(Participant, User)
            .join(User, User.id == Participant.user_id)
            .where(Participant.room_id.in_(ids))
        )
    ).all()

    buckets = Counter(min(4, d.confidence // 20) for d in decisions)
    confidence_distribution = [
        {"range": f"{b * 20}-{b * 20 + 19 if b < 4 else 100}", "count": buckets.get(b, 0)}
        for b in range(5)
    ]
    room_order = {r.id: i for i, r in enumerate(sorted(rooms, key=lambda r: r.created_at))}
    trends: dict[str, list[dict[str, Any]]] = defaultdict(list)
    user_of = {p.id: u for p, u in participants}
    for room_id, report in reports.items():
        room = next((r for r in rooms if r.id == room_id), None)
        if room is None:
            continue
        for pr in report.report_payload.get("participants", []):
            u = user_of.get(uuid.UUID(pr["participant_id"]))
            if u is None:
                continue
            trends[u.display_name].append(
                {
                    "room": room.name,
                    "order": room_order.get(room_id, 0),
                    "date": (room.ended_at or room.created_at).isoformat(),
                    "overall_score": pr["overall_score"],
                    "decision_quality": pr["decision_quality"],
                    "uncertainty_management": pr["uncertainty_management"],
                }
            )
    return {
        "total_exercises": len(rooms),
        "total_decisions": len(decisions),
        "average_response_time_s": m.mean(
            (d.response_time_ms / 1000 for d in decisions), default=0.0
        ),
        "average_uncertainty_at_decision": m.mean(
            (s.uncertainty_score for s in snapshots), default=0.0
        ),
        "average_coordination_score": m.mean(
            (
                r.report_payload.get("team", {}).get("average_coordination", 0)
                for r in reports.values()
            ),
            default=0.0,
        ),
        "average_team_score": m.mean((r.team_score for r in reports.values()), default=0.0),
        "reports_generated": len(reports),
        "confidence_distribution": confidence_distribution,
        "degradation_frequency": [
            {"type": t, "count": c}
            for t, c in Counter(d.disruption_type for d in disruptions).most_common()
        ],
        "delivery_outcomes": [{"status": s, "count": c} for s, c in statuses.most_common()],
        "participant_trends": [
            {"name": name, "points": sorted(points, key=lambda p: p["order"])}
            for name, points in trends.items()
        ],
        "exercises": [
            {
                "id": str(r.id),
                "name": r.name,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "team_score": reports[r.id].team_score if r.id in reports else None,
            }
            for r in rooms
        ],
    }


async def room_metric_series(session: AsyncSession, room: SimulationRoom) -> dict[str, Any]:
    rows = list(
        (
            await session.scalars(
                select(MetricSnapshot)
                .where(MetricSnapshot.room_id == room.id)
                .order_by(MetricSnapshot.sim_time)
            )
        ).all()
    )
    participants = {
        p.id: p.callsign
        for p in (
            await session.scalars(select(Participant).where(Participant.room_id == room.id))
        ).all()
    }
    series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = participants.get(r.participant_id, "TEAM") if r.participant_id else "TEAM"
        series[key].append(
            {
                "sim_time": r.sim_time,
                "uncertainty_index": r.uncertainty_index,
                "information_completeness": r.information_completeness,
                "information_reliability": r.information_reliability,
                "communication_health": r.communication_health,
            }
        )
    return {"series": series}
