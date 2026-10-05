"""Instructor live controls. Every action is persisted and appended to the audit stream."""

import uuid
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.deps import RoomInstructor, SessionDep
from app.core.errors import conflict, not_found
from app.core.text import require_text
from app.models.enums import ActorType, RoomStatus
from app.models.messaging import CommunicationDisruption
from app.models.room import InstructorNote, Participant
from app.scenario.clock import SystemClock
from app.scenario.engine import ScenarioEngine
from app.schemas.room import (
    ChannelUpdate,
    ConflictIn,
    DisruptionCreate,
    NoteIn,
    NoticeIn,
    TriggerEventIn,
)
from app.services.audit import commit_and_publish, record_event

router = APIRouter(tags=["controls"])
clock = SystemClock()


@router.patch(
    "/rooms/{room_id}/channels/{channel_id}", summary="Degrade / disable / restore / tune a channel"
)
async def update_channel(
    channel_id: uuid.UUID, body: ChannelUpdate, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    channel = await engine.update_channel(
        room, channel_id, body.model_dump(exclude_none=True), access.user.id
    )
    await commit_and_publish(session)
    return {
        "id": str(channel.id),
        "key": channel.key,
        "status": channel.status,
        "reliability": channel.reliability,
        "latency_ms": channel.latency_ms,
    }


@router.post(
    "/rooms/{room_id}/events/trigger",
    status_code=status.HTTP_201_CREATED,
    summary="Fire a scenario event now, or an ad-hoc instructor event",
)
async def trigger_event(
    body: TriggerEventIn, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    if body.template_key:
        event = await engine.trigger_template_event(room, body.template_key, access.user.id)
    else:
        assert body.custom is not None
        payload = body.custom.model_dump(mode="json")
        payload["title"] = require_text(payload["title"], 200)
        payload["content"] = require_text(payload["content"], 4000)
        event = await engine.trigger_custom_event(room, payload, access.user.id)
    await commit_and_publish(session)
    return {"scenario_event_id": str(event.id), "title": event.title, "sim_time": event.sim_time}


@router.post(
    "/rooms/{room_id}/notices",
    status_code=status.HTTP_201_CREATED,
    summary="Send a custom simulation notice",
)
async def send_notice(
    body: NoticeIn, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    engine._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
    participants = await engine.participants(room)
    wanted = {str(t) for t in body.target_participant_ids}
    recipients = [p for p in participants if not wanted or str(p.id) in wanted]
    sim = engine.now_sim(room)
    await engine.system_notice(
        room,
        require_text(body.title, 200),
        require_text(body.content, 2000),
        recipients,
        sim,
        actor_id=access.user.id,
        channel_key=body.channel_key,
        priority=body.priority.value,
    )
    await commit_and_publish(session)
    return {"recipients": [str(p.id) for p in recipients], "sim_time": sim}


@router.post(
    "/rooms/{room_id}/conflicts",
    status_code=status.HTTP_201_CREATED,
    summary="Inject a controlled conflicting report",
)
async def inject_conflict(
    body: ConflictIn, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    payload = body.model_dump(mode="json")
    payload["title"] = require_text(payload["title"], 200)
    payload["content"] = require_text(payload["content"], 4000)
    await engine.inject_conflict(room, payload, access.user.id)
    await commit_and_publish(session)
    return {"ok": True}


@router.post(
    "/rooms/{room_id}/disruptions",
    status_code=status.HTTP_201_CREATED,
    summary="Start a communication disruption",
)
async def create_disruption(
    body: DisruptionCreate, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    engine._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
    disruption = await engine.create_disruption(
        room,
        disruption_type=body.disruption_type.value,
        target_participant_ids=[str(p) for p in body.target_participant_ids],
        target_channel_ids=[str(c) for c in body.target_channel_ids],
        severity=body.severity,
        config=body.config(),
        duration_seconds=body.duration_seconds,
        actor_id=access.user.id,
        sim=engine.now_sim(room),
    )
    await commit_and_publish(session)
    return {
        "id": str(disruption.id),
        "disruption_type": disruption.disruption_type,
        "start_sim_time": disruption.start_sim_time,
    }


@router.post("/rooms/{room_id}/disruptions/{disruption_id}/end", summary="End a disruption")
async def end_disruption(
    disruption_id: uuid.UUID, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    engine._require(room, RoomStatus.RUNNING, RoomStatus.PAUSED)
    disruption = await session.get(CommunicationDisruption, disruption_id)
    if disruption is None or disruption.room_id != room.id:
        raise not_found("DISRUPTION_NOT_FOUND", "Disruption not found.")
    await engine.end_disruption(room, disruption, access.user.id, engine.now_sim(room))
    await commit_and_publish(session)
    return {"id": str(disruption.id), "end_sim_time": disruption.end_sim_time}


@router.post(
    "/rooms/{room_id}/decision-points/{key}/open",
    status_code=status.HTTP_201_CREATED,
    summary="Open a decision point now (manual trigger)",
)
async def open_decision_point(
    key: str, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    dp = await engine.open_decision_point_now(room, key, access.user.id)
    await commit_and_publish(session)
    return {"id": str(dp.id), "key": dp.key, "opened_sim_time": dp.opened_sim_time}


@router.get("/rooms/{room_id}/notes", summary="Instructor notes")
async def list_notes(access: RoomInstructor, session: SessionDep) -> list[dict[str, Any]]:
    notes = (
        await session.scalars(
            select(InstructorNote)
            .where(InstructorNote.room_id == access.room.id)
            .order_by(InstructorNote.sim_time)
        )
    ).all()
    return [
        {
            "id": str(n.id),
            "sim_time": n.sim_time,
            "content": n.content,
            "participant_id": str(n.participant_id) if n.participant_id else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]


@router.post(
    "/rooms/{room_id}/notes", status_code=status.HTTP_201_CREATED, summary="Add a timestamped note"
)
async def add_note(body: NoteIn, access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    room = access.room
    if room.status == RoomStatus.ARCHIVED:
        raise conflict("ROOM_ARCHIVED", "Archived exercises are read-only.")
    if body.participant_id is not None:
        p = await session.get(Participant, body.participant_id)
        if p is None or p.room_id != room.id:
            raise not_found("PARTICIPANT_NOT_FOUND", "Participant not found in this room.")
    sim = ScenarioEngine(session, clock).now_sim(room)
    note = InstructorNote(
        room_id=room.id,
        author_id=access.user.id,
        participant_id=body.participant_id,
        sim_time=sim,
        content=require_text(body.content, 2000),
    )
    session.add(note)
    await session.flush()
    await record_event(
        session,
        room.id,
        "note.created",
        {
            "note_id": str(note.id),
            "content": note.content,
            "participant_id": str(body.participant_id) if body.participant_id else None,
        },
        actor_id=access.user.id,
        actor_type=ActorType.USER,
        sim_time=sim,
    )
    await commit_and_publish(session)
    return {"id": str(note.id), "sim_time": sim, "content": note.content}
