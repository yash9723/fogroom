import uuid
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.deps import (
    CurrentUser,
    InstructorUser,
    RoomAccessDep,
    RoomInstructor,
    RoomParticipant,
    SessionDep,
)
from app.models.enums import ActorType, EventVisibility, RoomStatus, UserRole
from app.models.room import Participant, SimulationRoom
from app.scenario.clock import SystemClock
from app.scenario.engine import ScenarioEngine
from app.scenario.library.grey_signal import GREY_SIGNAL
from app.scenario.runner import runner
from app.schemas.room import (
    AdvanceClockIn,
    DemoLaunchIn,
    JoinByCodeIn,
    ParticipantUpdate,
    ReadyIn,
    RoomCreate,
)
from app.services import rooms as room_service
from app.services.audit import commit_and_publish, record_event
from app.services.live_state import room_summary

router = APIRouter(tags=["rooms"])
clock = SystemClock()


async def _summary(session: SessionDep, room: SimulationRoom) -> dict[str, Any]:
    return await room_summary(session, room, clock)


@router.post(
    "/rooms", status_code=status.HTTP_201_CREATED, summary="Create a training room (lobby)"
)
async def create_room(
    body: RoomCreate, user: InstructorUser, session: SessionDep
) -> dict[str, Any]:
    room = await room_service.create_room(
        session, user, body.scenario_id, body.name, body.time_scale
    )
    await commit_and_publish(session)
    return await _summary(session, room)


@router.post(
    "/demo/launch",
    status_code=status.HTTP_201_CREATED,
    summary="Launch the Operation Grey Signal demo room",
)
async def launch_demo(
    body: DemoLaunchIn, user: InstructorUser, session: SessionDep
) -> dict[str, Any]:
    scenario = await room_service.find_scenario_by_name(session, GREY_SIGNAL["name"])
    room = await room_service.create_room(
        session, user, scenario.id, f"{scenario.name} - Demo", body.time_scale
    )
    await commit_and_publish(session)
    return await _summary(session, room)


@router.get("/rooms", summary="Rooms visible to the current user")
async def list_rooms(user: CurrentUser, session: SessionDep) -> list[dict[str, Any]]:
    if user.role == UserRole.ADMIN:
        query = select(SimulationRoom)
    elif user.role == UserRole.INSTRUCTOR:
        query = select(SimulationRoom).where(SimulationRoom.instructor_id == user.id)
    else:
        query = (
            select(SimulationRoom)
            .join(Participant, Participant.room_id == SimulationRoom.id)
            .where(Participant.user_id == user.id)
        )
    rooms = (
        await session.scalars(query.order_by(SimulationRoom.created_at.desc()).limit(100))
    ).all()
    return [await _summary(session, r) for r in rooms]


@router.get("/rooms/{room_id}", summary="Room details (members only)")
async def get_room(access: RoomAccessDep, session: SessionDep) -> dict[str, Any]:
    return await _summary(session, access.room)


@router.post("/rooms/join", summary="Join a room using its room code")
async def join_by_code(
    body: JoinByCodeIn, user: CurrentUser, session: SessionDep
) -> dict[str, Any]:
    room = await room_service.find_room_by_code(session, body.room_code)
    participant, created = await room_service.join_room(session, room, user)
    await commit_and_publish(session)
    return {
        "room": await _summary(session, room),
        "participant_id": str(participant.id),
        "created": created,
    }


@router.post("/rooms/{room_id}/join", summary="Join a room by id")
async def join_by_id(room_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    room = await room_service.get_room(session, room_id)
    participant, created = await room_service.join_room(session, room, user)
    await commit_and_publish(session)
    return {
        "room": await _summary(session, room),
        "participant_id": str(participant.id),
        "created": created,
    }


async def _lifecycle(access: RoomInstructor, session: SessionDep, action: str) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    if action == "start":
        await engine.start(room, access.user.id)
    elif action == "pause":
        await engine.pause(room, access.user.id)
    elif action == "resume":
        await engine.resume(room, access.user.id)
    else:
        await engine.end(room, access.user.id)
    await commit_and_publish(session)
    if room.status in (RoomStatus.RUNNING, RoomStatus.PAUSED):
        runner.ensure_running(room.id)
    return await _summary(session, room)


@router.post("/rooms/{room_id}/start", summary="Start the exercise")
async def start_room(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    return await _lifecycle(access, session, "start")


@router.post("/rooms/{room_id}/pause", summary="Pause the simulation clock")
async def pause_room(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    return await _lifecycle(access, session, "pause")


@router.post("/rooms/{room_id}/resume", summary="Resume the simulation clock")
async def resume_room(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    return await _lifecycle(access, session, "resume")


@router.post("/rooms/{room_id}/end", summary="End the exercise (history becomes immutable)")
async def end_room(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    return await _lifecycle(access, session, "end")


@router.post("/rooms/{room_id}/clock/advance", summary="Fast-forward the simulation clock")
async def advance_clock(
    body: AdvanceClockIn, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(access.room.id)
    await engine.advance_clock(room, body.to_sim_seconds, access.user.id)
    await commit_and_publish(session)
    return await _summary(session, room)


@router.get("/rooms/{room_id}/participants", summary="Participants and their connection state")
async def list_participants(access: RoomAccessDep, session: SessionDep) -> list[dict[str, Any]]:
    summary = await _summary(session, access.room)
    participants: list[dict[str, Any]] = summary["participants"]
    return participants


@router.patch(
    "/rooms/{room_id}/participants/{participant_id}", summary="Assign a role / callsign (lobby)"
)
async def update_participant(
    participant_id: uuid.UUID, body: ParticipantUpdate, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    await room_service.update_participant(
        session,
        access.room,
        participant_id,
        role_key=body.role_key,
        callsign=body.callsign,
        actor=access.user,
    )
    await commit_and_publish(session)
    return await _summary(session, access.room)


@router.delete(
    "/rooms/{room_id}/participants/{participant_id}", summary="Remove a participant (lobby)"
)
async def remove_participant(
    participant_id: uuid.UUID, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    await room_service.remove_participant(session, access.room, participant_id, access.user)
    await commit_and_publish(session)
    return await _summary(session, access.room)


@router.post("/rooms/{room_id}/ready", summary="Mark yourself ready in the lobby")
async def set_ready(body: ReadyIn, access: RoomParticipant, session: SessionDep) -> dict[str, Any]:
    participant = access.participant
    assert participant is not None
    participant.is_ready = body.ready
    await record_event(
        session,
        access.room.id,
        "participant.ready",
        {
            "participant_id": str(participant.id),
            "callsign": participant.callsign,
            "ready": body.ready,
        },
        actor_id=access.user.id,
        actor_type=ActorType.USER,
        visibility=EventVisibility.ALL,
    )
    await commit_and_publish(session)
    return await _summary(session, access.room)
