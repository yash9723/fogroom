"""Append-only event stream.

`record_event` writes an AuditEvent with a per-room monotonically increasing `seq`
inside the caller's transaction. The event is queued on the session and only published
to Redis (and from there to WebSocket clients) after the transaction commits, via
`commit_and_publish`. PostgreSQL stays the source of truth; Redis is fan-out only.
"""

import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.enums import ActorType, EventVisibility
from app.models.room import SimulationRoom
from app.realtime.bus import publish_events

logger = logging.getLogger("fogroom.audit")

_PENDING_KEY = "fogroom_pending_events"


async def record_event(
    session: AsyncSession,
    room_id: uuid.UUID | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    actor_id: uuid.UUID | None = None,
    actor_type: ActorType = ActorType.SYSTEM,
    sim_time: float | None = None,
    visibility: EventVisibility = EventVisibility.INSTRUCTOR,
    targets: Iterable[uuid.UUID | str] | None = None,
) -> AuditEvent:
    seq: int | None = None
    if room_id is not None:
        result = await session.execute(
            update(SimulationRoom)
            .where(SimulationRoom.id == room_id)
            .values(event_seq=SimulationRoom.event_seq + 1)
            .returning(SimulationRoom.event_seq)
        )
        seq = result.scalar_one()
    event = AuditEvent(
        room_id=room_id,
        seq=seq,
        actor_id=actor_id,
        actor_type=actor_type.value,
        event_type=event_type,
        payload=payload or {},
        sim_time=sim_time,
        visibility=visibility.value,
        target_participant_ids=[str(t) for t in (targets or [])],
        timestamp=datetime.now(UTC),
    )
    session.add(event)
    if room_id is not None:
        session.info.setdefault(_PENDING_KEY, []).append(event)
    return event


def event_to_wire(event: AuditEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "room_id": str(event.room_id) if event.room_id else None,
        "event_type": event.event_type,
        "sim_time": event.sim_time,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "visibility": event.visibility,
        "targets": event.target_participant_ids,
        "actor_type": event.actor_type,
        "payload": event.payload,
    }


async def commit_and_publish(session: AsyncSession) -> None:
    """Commit the transaction, then fan out the events it produced."""
    pending: list[AuditEvent] = session.info.pop(_PENDING_KEY, [])
    await session.commit()
    if not pending:
        return
    wire = [event_to_wire(event) for event in pending]
    try:
        await publish_events(wire)
    except Exception:  # Redis hiccup: clients recover via /sync on reconnect
        logger.exception("Failed to publish %d room events", len(wire))


def discard_pending(session: AsyncSession) -> None:
    session.info.pop(_PENDING_KEY, None)
