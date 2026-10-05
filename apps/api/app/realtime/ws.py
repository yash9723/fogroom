"""WebSocket endpoint: /ws/rooms/{room_id}

Protocol (JSON frames):
  client -> {"type": "auth", "token": "<access JWT>"}         (must be first, within 10 s)
  server -> {"type": "hello", "last_seq": n, "role": ..., ...}
  server -> {"type": "event", "event": {...}}                  (filtered per viewer)
  client -> {"type": "ping"}   server -> {"type": "pong", "server_time": ...}

Tokens are sent in the first frame - never in the URL - so they never reach access logs.
On reconnect, clients call GET /api/v1/rooms/{id}/sync?since_seq=n to fetch missed events.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.deps import resolve_room_access, user_from_token
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import db
from app.models.enums import ActorType, ConnectionStatus, EventVisibility
from app.models.room import Participant
from app.realtime.manager import Connection, manager
from app.services.audit import commit_and_publish, record_event

logger = logging.getLogger("fogroom.ws")
router = APIRouter()

AUTH_TIMEOUT_SECONDS = 10.0


def _presence_key(room_id: uuid.UUID) -> str:
    return f"fogroom:presence:{room_id}"


async def _set_presence(
    room_id: uuid.UUID, participant_id: uuid.UUID, status: ConnectionStatus
) -> None:
    async with db.sessionmaker() as session:
        participant = await session.get(Participant, participant_id)
        if participant is None:
            return
        if participant.connection_status == status.value and status == ConnectionStatus.CONNECTED:
            participant.last_seen_at = datetime.now(UTC)
            await session.commit()
            return
        participant.connection_status = status.value
        participant.last_seen_at = datetime.now(UTC)
        await record_event(
            session,
            room_id,
            "presence.updated",
            {
                "participant_id": str(participant.id),
                "callsign": participant.callsign,
                "status": status.value,
            },
            actor_id=participant.user_id,
            actor_type=ActorType.USER,
            visibility=EventVisibility.ALL,
        )
        await commit_and_publish(session)


@router.websocket("/ws/rooms/{room_id}")
async def room_socket(websocket: WebSocket, room_id: uuid.UUID) -> None:
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        await websocket.close(code=4401, reason="Authentication required")
        return
    if not isinstance(first, dict) or first.get("type") != "auth" or not first.get("token"):
        await websocket.close(code=4401, reason="Authentication required")
        return

    try:
        async with db.sessionmaker() as session:
            user = await user_from_token(session, str(first["token"]))
            access = await resolve_room_access(session, room_id, user)
            last_seq = access.room.event_seq
            room_status = access.room.status
            participant_id = access.participant.id if access.participant else None
    except AppError as exc:
        await websocket.send_json({"type": "error", "code": exc.code, "message": exc.message})
        await websocket.close(code=4401 if exc.status_code == 401 else 4403, reason=exc.code)
        return

    conn = Connection(
        websocket=websocket,
        user_id=str(user.id),
        is_instructor=access.is_instructor,
        participant_id=str(participant_id) if participant_id else None,
    )
    # `hello` is always the first frame; events start flowing only after it.
    await conn.send(
        {
            "type": "hello",
            "room_id": str(room_id),
            "last_seq": last_seq,
            "room_status": room_status,
            "viewer": "INSTRUCTOR" if access.is_instructor else "TRAINEE",
            "participant_id": conn.participant_id,
        }
    )
    manager.add(str(room_id), conn)
    presence_member = str(participant_id or user.id)
    redis = get_redis()
    try:
        await redis.hincrby(_presence_key(room_id), presence_member, 1)
    except Exception:
        logger.warning("Presence update failed (Redis unavailable)")
    if participant_id:
        await _set_presence(room_id, participant_id, ConnectionStatus.CONNECTED)
    logger.info(
        "WS connected room=%s user=%s instructor=%s", room_id, user.id, access.is_instructor
    )

    try:
        while True:
            data = await websocket.receive_json()
            if isinstance(data, dict) and data.get("type") == "ping":
                await conn.send({"type": "pong", "server_time": datetime.now(UTC).isoformat()})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        manager.remove(str(room_id), conn)
        # Shielded so the disconnect is recorded even if the handler task is cancelled.
        cleanup = asyncio.ensure_future(_on_disconnect(room_id, presence_member, participant_id))
        try:
            await asyncio.shield(cleanup)
        finally:
            logger.info("WS disconnected room=%s user=%s", room_id, user.id)


async def _on_disconnect(
    room_id: uuid.UUID, presence_member: str, participant_id: uuid.UUID | None
) -> None:
    remaining = 0
    try:
        redis = get_redis()
        remaining = int(await redis.hincrby(_presence_key(room_id), presence_member, -1))
        if remaining <= 0:
            await redis.hdel(_presence_key(room_id), presence_member)
    except Exception:
        logger.warning("Presence cleanup failed (Redis unavailable)")
    if participant_id and remaining <= 0:
        try:
            await _set_presence(room_id, participant_id, ConnectionStatus.DISCONNECTED)
        except Exception:
            logger.exception("Failed to record disconnect")
