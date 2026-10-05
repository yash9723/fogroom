"""Access-control rules: trainees never see global truth or other participants' state."""

from typing import Any

from httpx import AsyncClient

from tests.conftest import Exercise, login


async def test_trainee_cannot_access_room_they_did_not_join(
    client: AsyncClient, exercise: Exercise
) -> None:
    outsider = await login(client, "delta")
    for path in ("", "/me", "/participants", "/sync"):
        resp = await client.get(exercise.url(path), headers=outsider)
        assert resp.status_code == 403, path
        assert resp.json()["error"]["code"] == "ROOM_ACCESS_DENIED"


async def test_trainee_cannot_read_global_truth_or_instructor_views(
    client: AsyncClient, exercise: Exercise
) -> None:
    h = exercise.h["alpha"]
    bravo = exercise.pid["bravo"]
    for path in (
        "/state",
        "/timeline",
        f"/participants/{bravo}/information-state",
        "/information-state/truth",
        "/aar",
        "/analytics",
        "/notes",
    ):
        resp = await client.get(exercise.url(path), headers=h)
        assert resp.status_code == 403, path


async def test_trainee_cannot_use_instructor_controls(
    client: AsyncClient, exercise: Exercise
) -> None:
    h = exercise.h["bravo"]
    assert (await client.post(exercise.url("/pause"), headers=h)).status_code == 403
    assert (await client.post(exercise.url("/end"), headers=h)).status_code == 403
    resp = await client.post(
        exercise.url("/events/trigger"), json={"template_key": "weather_update"}, headers=h
    )
    assert resp.status_code == 403
    assert (
        await client.post("/api/v1/scenarios", json={"name": "x"}, headers=h)
    ).status_code == 403


async def test_trainee_never_sees_undelivered_messages(
    client: AsyncClient, exercise: Exercise
) -> None:
    await exercise.advance(61)
    # Charlie's copy of "Bridge Orion inspection" was dropped; Bravo's is still in flight.
    assert "Bridge Orion inspection" in await exercise.titles("alpha")
    assert "Bridge Orion inspection" not in await exercise.titles("bravo")
    assert "Bridge Orion inspection" not in await exercise.titles("charlie")
    # Trainee view never exposes server message labels or fact keys.
    msg = (await exercise.me("alpha"))["messages"][0]
    assert "label" not in msg and "fact_key" not in msg


async def test_trainee_event_sync_is_filtered(client: AsyncClient, exercise: Exercise) -> None:
    await exercise.advance(61)
    events = (await client.get(exercise.url("/sync"), headers=exercise.h["charlie"])).json()[
        "events"
    ]
    types = {e["event_type"] for e in events}
    assert "message.created" not in types
    assert "message.dropped" not in types
    assert "message.delayed" not in types
    assert all("targets" not in e for e in events)
    # Instructor sees the drop.
    inst = (await client.get(exercise.url("/sync"), headers=exercise.h["instructor"])).json()[
        "events"
    ]
    assert any(
        e["event_type"] == "message.dropped" and e["payload"]["callsign"] == "CHARLIE" for e in inst
    )


async def test_instructor_cannot_access_another_instructors_room(
    client: AsyncClient, exercise: Exercise
) -> None:
    other = await login(client, "instructor2")
    assert (await client.get(exercise.url("/state"), headers=other)).status_code == 403
    assert (await client.post(exercise.url("/pause"), headers=other)).status_code == 403


async def test_admin_can_access_any_room(client: AsyncClient, exercise: Exercise) -> None:
    admin = await login(client, "admin")
    assert (await client.get(exercise.url("/state"), headers=admin)).status_code == 200


async def test_instructor_cannot_join_as_participant(
    client: AsyncClient, exercise: Exercise
) -> None:
    resp = await client.post(
        "/api/v1/rooms/join", json={"room_code": exercise.code}, headers=exercise.h["instructor"]
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_trainee_cannot_acknowledge_someone_elses_delivery(
    client: AsyncClient, exercise: Exercise
) -> None:
    alpha_msg = (await exercise.me("alpha"))["messages"][0]["id"]
    resp = await client.post(
        exercise.url(f"/messages/{alpha_msg}/ack"), headers=exercise.h["bravo"]
    )
    assert resp.status_code == 404


async def test_missing_room_returns_404(client: AsyncClient, seeded: dict[str, Any]) -> None:
    h = await login(client, "instructor")
    resp = await client.get("/api/v1/rooms/00000000-0000-0000-0000-000000000000", headers=h)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ROOM_NOT_FOUND"
