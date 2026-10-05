"""End-to-end backend integration: room -> join -> start -> degraded delivery -> decisions
-> end -> AAR -> historical information-state reconstruction."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import db
from app.models import InformationSnapshot, MessageDelivery, SimulationRoom
from app.scenario.clock import ManualClock
from app.scenario.engine import ScenarioEngine
from app.services.audit import commit_and_publish
from tests.conftest import Exercise, login


async def test_lobby_roles_join_and_duplicate_join(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    ex = await Exercise(client).setup(start=False)
    room = (await client.get(ex.url(""), headers=ex.h["instructor"])).json()
    roles = {p["callsign"]: p["assigned_role"] for p in room["participants"]}
    assert roles == {"ALPHA": "alpha", "BRAVO": "bravo", "CHARLIE": "charlie"}
    # Duplicate join is idempotent.
    again = await client.post(
        "/api/v1/rooms/join", json={"room_code": ex.code.lower()}, headers=ex.h["alpha"]
    )
    assert again.status_code == 200 and again.json()["created"] is False
    # Role swap keeps one-to-one mapping.
    swapped = await client.patch(
        ex.url(f"/participants/{ex.pid['alpha']}"),
        json={"role_key": "bravo"},
        headers=ex.h["instructor"],
    )
    assert swapped.status_code == 200
    roles = {p["id"]: p["assigned_role"] for p in swapped.json()["participants"]}
    assert roles[ex.pid["alpha"]] == "bravo" and roles[ex.pid["bravo"]] == "alpha"


async def test_cannot_start_twice_or_submit_before_start(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    ex = await Exercise(client).setup(start=False)
    resp = await client.post(
        ex.url("/decisions/medevac_method/submit"), json={"confidence": 50}, headers=ex.h["alpha"]
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "ROOM_NOT_RUNNING"
    assert (await client.post(ex.url("/start"), headers=ex.h["instructor"])).status_code == 200
    again = await client.post(ex.url("/start"), headers=ex.h["instructor"])
    assert again.status_code == 409


async def test_full_exercise_flow(client: AsyncClient, exercise: Exercise) -> None:  # noqa: PLR0915
    ex = exercise
    inst = ex.h["instructor"]

    # T+0 briefing reaches everyone.
    for persona in ("alpha", "bravo", "charlie"):
        assert "Initial situation briefing" in await ex.titles(persona)

    # Message A: Alpha immediately, Bravo +100 s, Charlie never.
    await ex.advance(61)
    assert "Bridge Orion inspection" in await ex.titles("alpha")
    assert "Bridge Orion inspection" not in await ex.titles("bravo")
    await ex.advance(165)
    assert "Bridge Orion inspection" in await ex.titles("bravo")
    assert "Bridge Orion inspection" not in await ex.titles("charlie")

    # Message B (conflicting) reaches Bravo; Alpha's copy is still in flight.
    await ex.advance(182)
    assert "Bridge Orion structural damage" in await ex.titles("bravo")
    assert "Bridge Orion structural damage" not in await ex.titles("alpha")

    bravo_state = await ex.info_state("bravo", 182)
    assert bravo_state["contradictions"][0]["fact_key"] == "bridge_orion_status"
    alpha_state = await ex.info_state("alpha", 182)
    pending = {p["title"]: p for p in alpha_state["pending"]}
    assert pending["Bridge Orion structural damage"]["eventual_outcome"] == "IN_FLIGHT"
    assert any(
        b["fact_key"] == "bridge_orion_status" and not b["accurate"] for b in alpha_state["beliefs"]
    )

    # Command Net degraded at T+120 - visible to trainees.
    channels = {c["key"]: c for c in (await ex.me("alpha"))["channels"]}
    assert channels["command"]["status"] == "DEGRADED"

    # Decision point opens at T+300.
    await ex.advance(301)
    dp = [d for d in (await ex.me("alpha"))["decision_points"] if d["key"] == "medevac_method"][0]
    assert dp["status"] == "OPEN"
    assert all("truth_alignment" not in o for o in dp["options"])

    submit = ex.url("/decisions/medevac_method/submit")
    r = await client.post(
        submit,
        json={
            "selected_option": "ground_bridge",
            "rationale": "Bridge reported open",
            "confidence": 80,
        },
        headers=ex.h["alpha"],
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        submit,
        json={
            "selected_option": "sea_harbor",
            "rationale": "Conflicting bridge reports",
            "confidence": 55,
        },
        headers=ex.h["bravo"],
    )
    assert r.status_code == 201
    dup = await client.post(
        submit,
        json={"selected_option": "sea_harbor", "rationale": "again", "confidence": 55},
        headers=ex.h["bravo"],
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ALREADY_SUBMITTED"
    missing_rationale = await client.post(
        submit, json={"selected_option": "hold_verify", "confidence": 40}, headers=ex.h["charlie"]
    )
    assert missing_rationale.status_code == 422

    # Pause blocks submission; resume allows it.
    assert (await client.post(ex.url("/pause"), headers=inst)).status_code == 200
    paused = await client.post(
        submit,
        json={"selected_option": "hold_verify", "rationale": "Need data", "confidence": 40},
        headers=ex.h["charlie"],
    )
    assert paused.status_code == 409 and paused.json()["error"]["code"] == "ROOM_PAUSED"
    assert (await client.post(ex.url("/resume"), headers=inst)).status_code == 200
    r = await client.post(
        submit,
        json={"selected_option": "hold_verify", "rationale": "Need data", "confidence": 40},
        headers=ex.h["charlie"],
    )
    assert r.status_code == 201

    # Every decision has a frozen information snapshot.
    async with db.sessionmaker() as session:
        snaps = (await session.scalars(select(InformationSnapshot))).all()
        assert len(snaps) == 3
        by_p = {str(s.participant_id): s for s in snaps}
        assert by_p[ex.pid["bravo"]].contradiction_count == 1
        assert by_p[ex.pid["alpha"]].contradiction_count == 0

    # All responses received -> decision point closed.
    state = (await client.get(ex.url("/state"), headers=inst)).json()
    assert (
        next(d for d in state["decision_points"] if d["key"] == "medevac_method")["status"]
        == "CLOSED"
    )

    # Late submission is rejected.
    await ex.advance(640)
    late = await client.post(
        ex.url("/decisions/logistics_route/submit"),
        json={"selected_option": "route_b_sea", "rationale": "late", "confidence": 60},
        headers=ex.h["alpha"],
    )
    assert late.status_code == 409 and late.json()["error"]["code"] == "DECISION_CLOSED"

    # Instructor controls: drop next message for Charlie, then broadcast an event.
    r = await client.post(
        ex.url("/disruptions"),
        json={
            "disruption_type": "DROPOUT",
            "drop_next": 1,
            "target_participant_ids": [ex.pid["charlie"]],
        },
        headers=inst,
    )
    assert r.status_code == 201
    r = await client.post(
        ex.url("/events/trigger"),
        json={
            "custom": {
                "title": "Fuel depot status",
                "content": "Fuel depot intact.",
                "importance_weight": 1,
            }
        },
        headers=inst,
    )
    assert r.status_code == 201
    assert "Fuel depot status" not in await ex.titles("charlie")

    # Conflict injection to Alpha only.
    r = await client.post(
        ex.url("/conflicts"),
        json={
            "fact_key": "harbor_delta_pier",
            "fact_value": "flooded",
            "title": "Pier flooding report",
            "content": "Pier reported flooded.",
            "target_participant_ids": [ex.pid["alpha"]],
        },
        headers=inst,
    )
    assert r.status_code == 201
    assert "Pier flooding report" in await ex.titles("alpha")
    assert "Pier flooding report" not in await ex.titles("bravo")

    # Channel control is logged and visible.
    command = next(c for c in state["channels"] if c["key"] == "medical")
    r = await client.patch(
        ex.url(f"/channels/{command['id']}"), json={"status": "OFFLINE"}, headers=inst
    )
    assert r.status_code == 200 and r.json()["status"] == "OFFLINE"
    r = await client.patch(
        ex.url(f"/channels/{command['id']}"), json={"restore": True}, headers=inst
    )
    assert r.json()["status"] == "ONLINE"

    note = await client.post(
        ex.url("/notes"),
        json={"content": "Bravo identified the conflicting reports."},
        headers=inst,
    )
    assert note.status_code == 201

    # Alpha's delayed copy of report B arrives at ~T+660.8 - after Alpha's decision.
    await ex.advance(670)
    assert "Bridge Orion structural damage" in await ex.titles("alpha")

    # End the exercise; history becomes immutable.
    assert (await client.post(ex.url("/end"), headers=inst)).status_code == 200
    blocked = await client.post(
        ex.url("/events/trigger"), json={"template_key": "weather_clearing"}, headers=inst
    )
    assert blocked.status_code == 409

    # AAR generation.
    aar = await client.post(ex.url("/aar/generate"), headers=inst)
    assert aar.status_code == 200, aar.text
    report = aar.json()["report"]
    assert report["exercise"]["participant_count"] == 3
    assert len(report["decisions"]) == 3
    assert report["notes"][0]["content"].startswith("Bravo identified")
    narratives = [line for o in report["information_outcomes"] for line in o["narrative"]]
    assert any("dropped for CHARLIE" in line for line in narratives)
    bravo_report = next(p for p in report["participants"] if p["callsign"] == "BRAVO")
    assert bravo_report["contradictions_encountered"] == 1
    assert aar.json()["narrative_source"] == "TEMPLATE" and aar.json()["narrative"]

    # Decision inspection shows available / missing / delayed / conflicting information.
    decisions = {d["callsign"]: d for d in report["decisions"]}
    alpha_insp = (
        await client.get(ex.url(f"/decisions/{decisions['ALPHA']['id']}/inspection"), headers=inst)
    ).json()
    later = [i["title"] for i in alpha_insp["delayed_information"]["arrived_after_decision"]]
    assert "Bridge Orion structural damage" in later
    assert any(i["title"] == "Bridge Orion inspection" for i in alpha_insp["available_information"])
    bravo_insp = (
        await client.get(ex.url(f"/decisions/{decisions['BRAVO']['id']}/inspection"), headers=inst)
    ).json()
    assert bravo_insp["conflicting_information"][0]["fact_key"] == "bridge_orion_status"
    charlie_insp = (
        await client.get(
            ex.url(f"/decisions/{decisions['CHARLIE']['id']}/inspection"), headers=inst
        )
    ).json()
    assert any(
        i["title"] == "Bridge Orion inspection"
        for i in charlie_insp["missing_information"]["dropped"]
    )

    # Historical reconstruction (replay) after the fact matches what happened live.
    alpha_100 = await ex.info_state("alpha", 100)
    bravo_100 = await ex.info_state("bravo", 100)
    charlie_100 = await ex.info_state("charlie", 100)
    assert "Bridge Orion inspection" in [m["title"] for m in alpha_100["received"]]
    assert (
        next(p for p in bravo_100["pending"] if p["title"] == "Bridge Orion inspection")[
            "eventual_outcome"
        ]
        == "DELIVERED_LATER"
    )
    assert "Bridge Orion inspection" in [m["title"] for m in charlie_100["dropped"]]

    truth = (
        await client.get(
            ex.url("/information-state/truth"), params={"timestamp": 200}, headers=inst
        )
    ).json()
    bridge_truth = next(f for f in truth["truth"]["facts"] if f["key"] == "bridge_orion_status")
    assert bridge_truth["value"] == "unusable"
    msg_a = next(m for m in truth["messages"] if m["title"] == "Bridge Orion inspection")
    assert {d["callsign"]: d["state"] for d in msg_a["deliveries"]} == {
        "ALPHA": "RECEIVED",
        "BRAVO": "RECEIVED",
        "CHARLIE": "DROPPED",
    }

    # Timeline filters.
    tl = (
        await client.get(ex.url("/timeline"), params={"event_type": "decision"}, headers=inst)
    ).json()
    assert tl["count"] >= 3 and all(e["event_type"].startswith("decision") for e in tl["events"])

    # PDF export.
    pdf = await client.get(ex.url("/aar/export.pdf"), headers=inst)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    # Analytics across completed exercises.
    overview = (await client.get("/api/v1/analytics/overview", headers=inst)).json()
    assert overview["total_exercises"] == 1 and overview["total_decisions"] == 3
    dash = (await client.get("/api/v1/dashboard", headers=inst)).json()
    assert dash["counts"]["completed"] == 1 and dash["recent_reports"]


async def test_engine_respects_pause_with_manual_clock(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    """Delayed deliveries follow simulation time: nothing arrives while paused."""
    ex = await Exercise(client).setup(start=False)
    clock = ManualClock()
    room_id = uuid.UUID(ex.room_id)
    instructor = uuid.UUID(seeded["users"]["instructor"])
    async with db.sessionmaker() as session:
        engine = ScenarioEngine(session, clock)
        room = await engine.lock_room(room_id)
        await engine.start(room, instructor)
        await commit_and_publish(session)

    async def tick() -> None:
        async with db.sessionmaker() as session:
            await ScenarioEngine(session, clock).tick(room_id)
            await commit_and_publish(session)

    async def bravo_bridge_status() -> str:
        async with db.sessionmaker() as session:
            rows = (
                await session.scalars(
                    select(MessageDelivery).where(
                        MessageDelivery.participant_id == uuid.UUID(ex.pid["bravo"])
                    )
                )
            ).all()
            from app.models import Message

            for d in rows:
                msg = await session.get(Message, d.message_id)
                if msg and msg.title == "Bridge Orion inspection":
                    return d.delivery_status
        return "NONE"

    clock.advance(60.5)
    await tick()
    assert await bravo_bridge_status() == "DELAYED"

    async with db.sessionmaker() as session:
        engine = ScenarioEngine(session, clock)
        room = await engine.lock_room(room_id)
        await engine.pause(room, instructor)
        await commit_and_publish(session)
    clock.advance(500)  # wall time passes while paused
    await tick()
    assert await bravo_bridge_status() == "DELAYED"

    async with db.sessionmaker() as session:
        engine = ScenarioEngine(session, clock)
        room = await engine.lock_room(room_id)
        await engine.resume(room, instructor)
        await commit_and_publish(session)
        assert room.sim_anchor_seconds == 60.5
    clock.advance(101)
    await tick()
    assert await bravo_bridge_status() == "DELIVERED"
    async with db.sessionmaker() as session:
        room_row = await session.get(SimulationRoom, room_id)
        assert room_row is not None and room_row.total_pause_seconds == 500.0


async def test_blackout_holds_then_releases(client: AsyncClient, exercise: Exercise) -> None:
    inst = exercise.h["instructor"]
    r = await client.post(
        exercise.url("/disruptions"),
        json={"disruption_type": "BLACKOUT", "target_participant_ids": [exercise.pid["bravo"]]},
        headers=inst,
    )
    disruption_id = r.json()["id"]
    me = await exercise.me("bravo")
    assert me["blackout"] is True and all(c["status"] == "OFFLINE" for c in me["channels"])
    await client.post(
        exercise.url("/notices"),
        json={
            "content": "Status check",
            "channel_key": "command",
            "target_participant_ids": [exercise.pid["bravo"]],
        },
        headers=inst,
    )
    assert "Exercise notice" not in await exercise.titles("bravo")
    # Team chat from a blacked-out participant fails.
    tm = await client.post(
        exercise.url("/team-messages"),
        json={"channel_key": "command", "message": "hello?"},
        headers=exercise.h["bravo"],
    )
    assert tm.json()["delivery_status"] == "FAILED"
    await client.post(exercise.url(f"/disruptions/{disruption_id}/end"), headers=inst)
    await exercise.advance(5)
    assert "Exercise notice" in await exercise.titles("bravo")


async def test_team_messages_respect_channels(client: AsyncClient, exercise: Exercise) -> None:
    ok = await client.post(
        exercise.url("/team-messages"),
        json={"channel_key": "logistics", "message": "Bridge?"},
        headers=exercise.h["alpha"],
    )
    assert ok.status_code == 201 and ok.json()["delivery_status"] == "DELIVERED"
    bravo_view = (await exercise.me("bravo"))["team_messages"]
    assert bravo_view[0]["message"] == "Bridge?" and bravo_view[0]["sender_callsign"] == "ALPHA"
    offline = await client.post(
        exercise.url("/team-messages"),
        json={"channel_key": "backup", "message": "test"},
        headers=exercise.h["alpha"],
    )
    assert offline.json()["delivery_status"] == "FAILED"
    assert "offline" in offline.json()["failure_reason"]


async def test_acknowledgement_is_recorded(client: AsyncClient, exercise: Exercise) -> None:
    msg = (await exercise.me("alpha"))["messages"][0]
    r = await client.post(exercise.url(f"/messages/{msg['id']}/ack"), headers=exercise.h["alpha"])
    assert r.status_code == 200 and r.json()["acknowledged_sim_time"] is not None
    assert (await exercise.me("alpha"))["messages"][0]["acknowledged"] is True


async def test_aar_requires_completed_exercise(client: AsyncClient, exercise: Exercise) -> None:
    resp = await client.post(exercise.url("/aar/generate"), headers=exercise.h["instructor"])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "ROOM_NOT_COMPLETED"


async def test_manual_decision_point_and_event_trigger(
    client: AsyncClient, exercise: Exercise
) -> None:
    inst = exercise.h["instructor"]
    r = await client.post(exercise.url("/decision-points/final_allocation/open"), headers=inst)
    assert r.status_code == 201
    again = await client.post(exercise.url("/decision-points/final_allocation/open"), headers=inst)
    assert again.status_code == 409
    r = await client.post(
        exercise.url("/events/trigger"), json={"template_key": "weather_update"}, headers=inst
    )
    assert r.status_code == 201
    twice = await client.post(
        exercise.url("/events/trigger"), json={"template_key": "weather_update"}, headers=inst
    )
    assert twice.status_code == 409
    await login(client, "alpha")
