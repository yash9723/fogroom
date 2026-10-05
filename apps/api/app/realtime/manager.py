"""In-process registry of WebSocket connections, with per-viewer event filtering."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.realtime.visibility import strip_for_trainee, wire_event_visible

logger = logging.getLogger("fogroom.ws")


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    user_id: str
    is_instructor: bool
    participant_id: str | None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, data: dict[str, Any]) -> None:
        async with self.lock:
            await self.websocket.send_json(data)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[Connection]] = {}

    def add(self, room_id: str, conn: Connection) -> None:
        self._rooms.setdefault(room_id, set()).add(conn)

    def remove(self, room_id: str, conn: Connection) -> None:
        conns = self._rooms.get(room_id)
        if conns is not None:
            conns.discard(conn)
            if not conns:
                self._rooms.pop(room_id, None)

    def count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, ()))

    async def dispatch(self, room_id: str, event: dict[str, Any]) -> None:
        """Deliver an event to every local connection allowed to see it."""
        for conn in list(self._rooms.get(room_id, ())):
            if not wire_event_visible(
                event, is_instructor=conn.is_instructor, participant_id=conn.participant_id
            ):
                continue
            body = event if conn.is_instructor else strip_for_trainee(event)
            try:
                await conn.send({"type": "event", "event": body})
            except Exception:
                logger.info("Dropping dead WebSocket for user %s", conn.user_id)
                self.remove(room_id, conn)


manager = ConnectionManager()
