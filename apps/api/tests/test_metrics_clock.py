"""Unit tests for the uncertainty metrics and the simulation clock."""

from datetime import UTC, datetime, timedelta

from app.models.enums import RoomStatus
from app.models.room import SimulationRoom
from app.scenario.clock import pause_clock, resume_clock, sim_now, start_clock, stop_clock
from app.services import metrics as m


def test_completeness_is_importance_weighted() -> None:
    items = [m.IntendedItem(3, True), m.IntendedItem(1, False)]
    assert m.completeness(items) == 75.0


def test_altered_information_gets_partial_credit() -> None:
    assert m.completeness([m.IntendedItem(2, True, altered=True)]) == 50.0


def test_reliability_weighted_by_source_and_path() -> None:
    items = [m.ReceivedItem(1, "HIGH", 1.0), m.ReceivedItem(1, "LOW", 1.0)]
    assert m.reliability(items) == 60.0  # (0.9 + 0.3) / 2


def test_communication_health_treats_offline_as_zero() -> None:
    items = [m.ChannelHealthItem(2, "ONLINE", 0.9), m.ChannelHealthItem(1, "OFFLINE", 0.9)]
    assert m.communication_health(items) == 60.0


def test_uncertainty_formula_and_contradiction_penalty() -> None:
    ics = m.information_confidence(100, 100, 100, 0)
    assert ics == 100.0
    assert m.uncertainty_index(80, 60, 50, 0) == round(100 - (0.4 * 80 + 0.3 * 60 + 0.3 * 50), 1)
    # penalty is bounded at 30
    assert m.information_confidence(100, 100, 100, 9) == 70.0


def test_calibration_and_response_scores() -> None:
    assert m.calibration_score(70, 70) == 100.0
    assert m.calibration_score(90, 40) == 50.0
    assert m.response_score(0, 120) == 100.0
    assert m.response_score(120, 120) == 50.0


def _room() -> SimulationRoom:
    return SimulationRoom(status=RoomStatus.RUNNING.value, time_scale=1.0, sim_anchor_seconds=0.0)


def test_clock_runs_pauses_and_resumes() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    room = _room()
    start_clock(room, t0)
    assert sim_now(room, t0 + timedelta(seconds=30)) == 30.0

    pause_clock(room, t0 + timedelta(seconds=30))
    room.status = RoomStatus.PAUSED.value
    # Clock frozen while paused
    assert sim_now(room, t0 + timedelta(seconds=500)) == 30.0

    resume_clock(room, t0 + timedelta(seconds=500))
    room.status = RoomStatus.RUNNING.value
    assert sim_now(room, t0 + timedelta(seconds=510)) == 40.0
    assert room.total_pause_seconds == 470.0

    final = stop_clock(room, t0 + timedelta(seconds=520))
    room.status = RoomStatus.COMPLETED.value
    assert final == 50.0
    assert sim_now(room, t0 + timedelta(days=1)) == 50.0


def test_time_scale_accelerates_simulation_time() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    room = _room()
    room.time_scale = 5.0
    start_clock(room, t0)
    assert sim_now(room, t0 + timedelta(seconds=12)) == 60.0
