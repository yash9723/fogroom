"""FastAPI authorization dependencies. The server verifies every permission;
frontend route guards are a convenience only."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, not_found, unauthorized
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.room import Participant, SimulationRoom
from app.models.user import User

_bearer = HTTPBearer(auto_error=False, description="JWT access token")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def user_from_token(session: AsyncSession, token: str) -> User:
    payload = decode_access_token(token)
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise unauthorized("Invalid access token.", "TOKEN_INVALID") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("Account unavailable.", "ACCOUNT_DISABLED")
    return user


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    return await user_from_token(session, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    allowed = {r.value for r in roles}

    async def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise forbidden("Your role is not permitted to perform this action.", "FORBIDDEN_ROLE")
        return user

    return _check


InstructorUser = Annotated[User, Depends(require_roles(UserRole.INSTRUCTOR, UserRole.ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


@dataclass
class RoomAccess:
    room: SimulationRoom
    user: User
    participant: Participant | None
    is_instructor: bool


async def resolve_room_access(session: AsyncSession, room_id: uuid.UUID, user: User) -> RoomAccess:
    room = await session.get(SimulationRoom, room_id)
    if room is None:
        raise not_found("ROOM_NOT_FOUND", "Room not found.")
    is_instructor = user.role == UserRole.ADMIN or (
        user.role == UserRole.INSTRUCTOR and room.instructor_id == user.id
    )
    participant = await session.scalar(
        select(Participant).where(Participant.room_id == room.id, Participant.user_id == user.id)
    )
    if not is_instructor and participant is None:
        raise forbidden("You are not a member of this exercise.", "ROOM_ACCESS_DENIED")
    return RoomAccess(room=room, user=user, participant=participant, is_instructor=is_instructor)


async def get_room_access(room_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> RoomAccess:
    return await resolve_room_access(session, room_id, user)


RoomAccessDep = Annotated[RoomAccess, Depends(get_room_access)]


async def room_instructor(access: RoomAccessDep) -> RoomAccess:
    if not access.is_instructor:
        raise forbidden("Only the exercise instructor can perform this action.", "INSTRUCTOR_ONLY")
    return access


async def room_participant(access: RoomAccessDep) -> RoomAccess:
    if access.participant is None:
        raise forbidden("Only exercise participants can perform this action.", "PARTICIPANT_ONLY")
    return access


RoomInstructor = Annotated[RoomAccess, Depends(room_instructor)]
RoomParticipant = Annotated[RoomAccess, Depends(room_participant)]
