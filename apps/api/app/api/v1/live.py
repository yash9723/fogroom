from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.auth.deps import RoomAccessDep, RoomInstructor, RoomParticipant, SessionDep
from app.models.audit import AuditEvent
from app.realtime.visibility import is_visible, strip_for_trainee
from app.scenario.clock import SystemClock
from app.services.audit import event_to_wire
from app.services.live_state import instructor_state, trainee_state

router = APIRouter(tags=["live"])
clock = SystemClock()


@router.get("/rooms/{room_id}/state", summary="Live instructor console state (global truth)")
async def get_instructor_state(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    return await instructor_state(session, access.room, clock)


@router.get("/rooms/{room_id}/me", summary="Trainee dashboard state - only delivered information")
async def get_trainee_state(access: RoomParticipant, session: SessionDep) -> dict[str, Any]:
    assert access.participant is not None
    return await trainee_state(session, access.room, access.participant, clock)


@router.get("/rooms/{room_id}/sync", summary="Events missed since a sequence number (reconnect)")
async def sync_events(
    access: RoomAccessDep,
    session: SessionDep,
    since_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.room_id == access.room.id, AuditEvent.seq > since_seq)
            .order_by(AuditEvent.seq)
            .limit(limit)
        )
    ).all()
    pid = str(access.participant.id) if access.participant else None
    events = []
    for e in rows:
        if is_visible(
            e.visibility,
            e.target_participant_ids,
            is_instructor=access.is_instructor,
            participant_id=pid,
        ):
            wire = event_to_wire(e)
            events.append(wire if access.is_instructor else strip_for_trainee(wire))
    last = rows[-1].seq if rows else since_seq
    return {"events": events, "last_seq": last, "room_status": access.room.status}


@router.get("/rooms/{room_id}/timeline", summary="Full audit timeline with filters (instructor)")
async def timeline(
    access: RoomInstructor,
    session: SessionDep,
    event_type: Annotated[list[str] | None, Query()] = None,
    participant_id: str | None = None,
    channel_key: str | None = None,
    decisions_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=5000)] = 2000,
) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.room_id == access.room.id)
            .order_by(AuditEvent.seq)
            .limit(limit)
        )
    ).all()
    out = []
    for e in rows:
        if event_type and not any(
            e.event_type == t or e.event_type.startswith(f"{t}.") for t in event_type
        ):
            continue
        if decisions_only and not e.event_type.startswith("decision."):
            continue
        payload = e.payload or {}
        if participant_id and not (
            payload.get("participant_id") == participant_id
            or participant_id in (e.target_participant_ids or [])
            or participant_id in (payload.get("recipient_ids") or [])
            or participant_id in (payload.get("target_participant_ids") or [])
            or payload.get("sender_participant_id") == participant_id
        ):
            continue
        if (
            channel_key
            and payload.get("channel_key") != channel_key
            and payload.get("key") != channel_key
        ):
            continue
        out.append(event_to_wire(e))
    return {"events": out, "count": len(out)}
