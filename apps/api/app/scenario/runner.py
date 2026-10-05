"""Background tick loop - one asyncio task per running room.

A Redis lock (SET NX PX) guarantees that only one API worker ticks a given room, so the
system can be scaled to several workers. On startup every RUNNING room is resumed:
delayed deliveries are persisted in PostgreSQL with simulation-time schedules, so they
survive restarts and are delivered on the next tick.
"""

import asyncio
import logging
import os
import socket
import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import db
from app.models.enums import RoomStatus
from app.models.room import SimulationRoom
from app.scenario.engine import ScenarioEngine
from app.services.audit import commit_and_publish, discard_pending

logger = logging.getLogger("fogroom.runner")

LOCK_TTL_MS = 5000
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


class EngineRunner:
    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}

    def ensure_running(self, room_id: uuid.UUID) -> None:
        if not settings.engine_autorun:
            return
        task = self._tasks.get(room_id)
        if task is None or task.done():
            self._tasks[room_id] = asyncio.create_task(
                self._loop(room_id), name=f"engine-{room_id}"
            )

    async def resume_all(self) -> None:
        async with db.sessionmaker() as session:
            ids = (
                await session.scalars(
                    select(SimulationRoom.id).where(
                        SimulationRoom.status.in_([RoomStatus.RUNNING, RoomStatus.PAUSED])
                    )
                )
            ).all()
        for room_id in ids:
            self.ensure_running(room_id)
        if ids:
            logger.info("Resumed engine loops for %d active rooms", len(ids))

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def _acquire(self, room_id: uuid.UUID) -> bool:
        redis = get_redis()
        key = f"fogroom:engine:room:{room_id}"
        if await redis.set(key, WORKER_ID, nx=True, px=LOCK_TTL_MS):
            return True
        if await redis.get(key) == WORKER_ID:
            await redis.pexpire(key, LOCK_TTL_MS)
            return True
        return False

    async def _loop(self, room_id: uuid.UUID) -> None:
        logger.info("Engine loop started for room %s", room_id)
        while True:
            try:
                if await self._acquire(room_id):
                    async with db.sessionmaker() as session:
                        engine = ScenarioEngine(session)
                        room = await engine.lock_room(room_id)
                        status = room.status
                        if status == RoomStatus.RUNNING:
                            await engine.process(room, engine.now_sim(room))
                            await commit_and_publish(session)
                        else:
                            discard_pending(session)
                            await session.rollback()
                        if status in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED):
                            logger.info("Engine loop finished for room %s", room_id)
                            return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Engine tick failed for room %s", room_id)
            await asyncio.sleep(settings.engine_tick_seconds)


runner = EngineRunner()
