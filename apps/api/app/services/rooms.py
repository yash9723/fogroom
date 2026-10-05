"""Room lifecycle helpers: creation (with frozen scenario snapshot), joining, roles."""

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict, forbidden, not_found
from app.models.enums import ActorType, EventVisibility, RoomStatus, UserRole
from app.models.room import CommunicationChannel, Participant, SimulationRoom
from app.models.scenario import ScenarioTemplate
from app.models.user import User
from app.scenario.loader import get_scenario, scenario_snapshot
from app.services.audit import record_event

_SKIP_WORDS = {"operation", "exercise", "scenario", "the"}


def code_prefix(name: str) -> str:
    for word in name.split():
        letters = "".join(ch for ch in word if ch.isalpha())
        if letters and letters.lower() not in _SKIP_WORDS:
            return letters[:5].upper()
    return "FOG"


async def generate_room_code(session: AsyncSession, scenario_name: str) -> str:
    prefix = code_prefix(scenario_name)
    for attempt in range(60):
        number = secrets.randbelow(90) + 10 if attempt < 30 else secrets.randbelow(900) + 100
        code = f"{prefix}-{number}"
        exists = await session.scalar(
            select(SimulationRoom.id).where(SimulationRoom.room_code == code)
        )
        if exists is None:
            return code
    raise AppError("ROOM_CODE_EXHAUSTED", "Could not allocate a room code, try again.", 503)


def normalize_code(code: str) -> str:
    return code.strip().upper().replace(" ", "")


async def create_room(
    session: AsyncSession,
    instructor: User,
    scenario_id: uuid.UUID,
    name: str | None,
    time_scale: float = 1.0,
) -> SimulationRoom:
    scenario = await get_scenario(session, scenario_id)
    snapshot = scenario_snapshot(scenario)
    room = SimulationRoom(
        room_code=await generate_room_code(session, scenario.name),
        name=(name or scenario.name).strip()[:200],
        scenario_template_id=scenario.id,
        instructor_id=instructor.id,
        status=RoomStatus.LOBBY.value,
        seed=secrets.randbits(62),
        time_scale=time_scale,
        scenario_snapshot=snapshot,
        settings={},
    )
    session.add(room)
    await session.flush()
    for i, ch in enumerate(snapshot.get("channels", [])):
        session.add(
            CommunicationChannel(
                room_id=room.id,
                key=ch["key"],
                name=ch["name"],
                channel_type=ch.get("channel_type", "VOICE"),
                status=ch.get("initial_status", "ONLINE"),
                reliability=ch.get("reliability", 0.95),
                latency_ms=ch.get("latency_ms", 500),
                weight=ch.get("weight", 1.0),
                fallback_channel_key=ch.get("fallback_channel_key"),
                sort_order=i,
            )
        )
    await record_event(
        session,
        room.id,
        "room.created",
        {
            "room_code": room.room_code,
            "name": room.name,
            "scenario": scenario.name,
            "time_scale": time_scale,
        },
        actor_id=instructor.id,
        actor_type=ActorType.USER,
        sim_time=0.0,
    )
    return room


async def get_room(session: AsyncSession, room_id: uuid.UUID) -> SimulationRoom:
    room = await session.get(SimulationRoom, room_id)
    if room is None:
        raise not_found("ROOM_NOT_FOUND", "Room not found.")
    return room


async def find_room_by_code(session: AsyncSession, code: str) -> SimulationRoom:
    room = await session.scalar(
        select(SimulationRoom).where(func.upper(SimulationRoom.room_code) == normalize_code(code))
    )
    if room is None:
        raise not_found("ROOM_NOT_FOUND", "No exercise found with that room code.")
    return room


async def participants_of(session: AsyncSession, room_id: uuid.UUID) -> list[Participant]:
    result = await session.scalars(
        select(Participant).where(Participant.room_id == room_id).order_by(Participant.joined_at)
    )
    return list(result.all())


def _roles(room: SimulationRoom) -> list[dict[str, str]]:
    return list((room.scenario_snapshot or {}).get("roles", []))


async def join_room(
    session: AsyncSession, room: SimulationRoom, user: User
) -> tuple[Participant, bool]:
    """Idempotent join: a duplicate join returns the existing participant."""
    if user.role != UserRole.TRAINEE:
        raise forbidden(
            "Only trainee accounts can join an exercise as a participant.", "FORBIDDEN_ROLE"
        )
    existing = await session.scalar(
        select(Participant).where(Participant.room_id == room.id, Participant.user_id == user.id)
    )
    if existing is not None:
        return existing, False
    if room.status in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED):
        raise conflict("ROOM_CLOSED", "This exercise has already finished.")

    participants = await participants_of(session, room.id)
    taken = {p.assigned_role for p in participants if p.assigned_role}
    free = [r for r in _roles(room) if r["key"] not in taken]
    local = user.email.split("@", 1)[0].lower()
    role = next((r for r in free if r["key"] == local), free[0] if free else None)

    participant = Participant(
        room_id=room.id,
        user_id=user.id,
        callsign=(role["callsign"] if role else user.display_name.upper())[:40],
        assigned_role=role["key"] if role else None,
        team=role.get("team") if role else None,
    )
    session.add(participant)
    try:
        await session.flush()
    except IntegrityError as exc:  # concurrent duplicate join
        await session.rollback()
        raise conflict("ALREADY_JOINED", "You have already joined this exercise.") from exc
    await record_event(
        session,
        room.id,
        "participant.joined",
        {
            "participant_id": str(participant.id),
            "callsign": participant.callsign,
            "display_name": user.display_name,
            "role": participant.assigned_role,
        },
        actor_id=user.id,
        actor_type=ActorType.USER,
        visibility=EventVisibility.ALL,
    )
    return participant, True


async def update_participant(
    session: AsyncSession,
    room: SimulationRoom,
    participant_id: uuid.UUID,
    *,
    role_key: str | None,
    callsign: str | None,
    actor: User,
) -> Participant:
    participant = await session.get(Participant, participant_id)
    if participant is None or participant.room_id != room.id:
        raise not_found("PARTICIPANT_NOT_FOUND", "Participant not found in this room.")
    if role_key is not None:
        if room.status != RoomStatus.LOBBY:
            raise conflict("ROOM_ALREADY_STARTED", "Roles can only be changed in the lobby.")
        role = next((r for r in _roles(room) if r["key"] == role_key), None)
        if role is None:
            raise AppError(
                "ROLE_NOT_FOUND", f"Role '{role_key}' does not exist in this scenario.", 422
            )
        holder = await session.scalar(
            select(Participant).where(
                Participant.room_id == room.id,
                Participant.assigned_role == role_key,
                Participant.id != participant.id,
            )
        )
        if holder is not None:
            # Swap roles so assignment is always a valid one-to-one mapping.
            holder.assigned_role = participant.assigned_role
            old = next((r for r in _roles(room) if r["key"] == participant.assigned_role), None)
            holder.callsign = old["callsign"] if old else holder.callsign
        participant.assigned_role = role_key
        participant.team = role.get("team")
        participant.callsign = role["callsign"]
    if callsign:
        participant.callsign = callsign.strip()[:40]
    await record_event(
        session,
        room.id,
        "participant.updated",
        {
            "participant_id": str(participant.id),
            "callsign": participant.callsign,
            "role": participant.assigned_role,
        },
        actor_id=actor.id,
        actor_type=ActorType.USER,
        visibility=EventVisibility.ALL,
    )
    return participant


async def remove_participant(
    session: AsyncSession, room: SimulationRoom, participant_id: uuid.UUID, actor: User
) -> None:
    participant = await session.get(Participant, participant_id)
    if participant is None or participant.room_id != room.id:
        raise not_found("PARTICIPANT_NOT_FOUND", "Participant not found in this room.")
    if room.status != RoomStatus.LOBBY:
        raise conflict("ROOM_ALREADY_STARTED", "Participants can only be removed in the lobby.")
    await record_event(
        session,
        room.id,
        "participant.left",
        {
            "participant_id": str(participant.id),
            "callsign": participant.callsign,
            "removed_by": "instructor",
        },
        actor_id=actor.id,
        actor_type=ActorType.USER,
        visibility=EventVisibility.ALL,
    )
    await session.delete(participant)


async def find_scenario_by_name(session: AsyncSession, name: str) -> ScenarioTemplate:
    scenario = await session.scalar(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.name == name)
        .order_by(ScenarioTemplate.created_at)
    )
    if scenario is None:
        raise not_found(
            "SCENARIO_NOT_FOUND", f"Scenario '{name}' is not seeded. Run the seed command."
        )
    return scenario
