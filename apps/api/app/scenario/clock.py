"""Simulation clock utilities.

The simulation clock is anchored rather than derived from `started_at`:

    sim_now = sim_anchor_seconds + (wall_now - anchor_at) * time_scale   (while RUNNING)
    sim_now = sim_anchor_seconds                                         (while PAUSED)

Pausing folds elapsed time into `sim_anchor_seconds` and clears `anchor_at`, so the
clock stops; resuming sets a new `anchor_at`. All schedules are stored in simulation
seconds, which makes pause/resume and time-scaling correct by construction.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.models.enums import RoomStatus
from app.models.room import SimulationRoom


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class ManualClock:
    """Deterministic clock for tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> datetime:
        self._now = self._now + timedelta(seconds=seconds)
        return self._now


def sim_now(room: SimulationRoom, wall_now: datetime) -> float:
    status = room.status
    if status == RoomStatus.RUNNING and room.anchor_at is not None:
        elapsed = (wall_now - room.anchor_at).total_seconds()
        return round(room.sim_anchor_seconds + max(0.0, elapsed) * room.time_scale, 3)
    if status in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED):
        return (
            room.final_sim_seconds
            if room.final_sim_seconds is not None
            else room.sim_anchor_seconds
        )
    if status == RoomStatus.PAUSED:
        return room.sim_anchor_seconds
    return 0.0


def wall_at(room: SimulationRoom, sim_time: float, wall_now: datetime) -> datetime | None:
    """Best-effort wall-clock estimate of a future simulation time (None if paused)."""
    if room.status != RoomStatus.RUNNING or room.anchor_at is None or room.time_scale <= 0:
        return None
    current = sim_now(room, wall_now)
    return wall_now + timedelta(seconds=(sim_time - current) / room.time_scale)


def start_clock(room: SimulationRoom, wall_now: datetime) -> None:
    room.started_at = wall_now
    room.sim_anchor_seconds = 0.0
    room.anchor_at = wall_now
    room.total_pause_seconds = 0.0
    room.paused_at = None


def pause_clock(room: SimulationRoom, wall_now: datetime) -> float:
    current = sim_now(room, wall_now)
    room.sim_anchor_seconds = current
    room.anchor_at = None
    room.paused_at = wall_now
    return current


def resume_clock(room: SimulationRoom, wall_now: datetime) -> float:
    if room.paused_at is not None:
        room.total_pause_seconds += (wall_now - room.paused_at).total_seconds()
    room.paused_at = None
    room.anchor_at = wall_now
    return room.sim_anchor_seconds


def stop_clock(room: SimulationRoom, wall_now: datetime) -> float:
    current = sim_now(room, wall_now)
    room.final_sim_seconds = current
    room.sim_anchor_seconds = current
    room.anchor_at = None
    return current


def format_sim_time(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"T+{total // 60:02d}:{total % 60:02d}"
