import copy
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.scenario.library.grey_signal import GREY_SIGNAL
from app.schemas.scenario import ScenarioCreate
from tests.conftest import login


def test_grey_signal_definition_is_valid() -> None:
    data = ScenarioCreate.model_validate(GREY_SIGNAL)
    assert {r.key for r in data.roles} == {"alpha", "bravo", "charlie"}
    assert len(data.decision_points) >= 3
    assert any(e.variants for e in data.events)


def test_invalid_references_are_rejected() -> None:
    bad = copy.deepcopy(GREY_SIGNAL)
    bad["events"][1]["channel_key"] = "nonexistent"
    with pytest.raises(ValidationError, match="unknown channel"):
        ScenarioCreate.model_validate(bad)

    bad = copy.deepcopy(GREY_SIGNAL)
    bad["events"][1]["targeting_rules"]["overrides"]["zulu"] = {"action": "drop"}
    with pytest.raises(ValidationError, match="unknown role"):
        ScenarioCreate.model_validate(bad)


async def test_scenario_crud(client: AsyncClient, seeded: dict[str, Any]) -> None:
    h = await login(client, "instructor")
    listed = (await client.get("/api/v1/scenarios", headers=h)).json()
    assert listed[0]["name"] == "Operation Grey Signal"
    assert listed[0]["decision_count"] == 4

    detail = (await client.get(f"/api/v1/scenarios/{seeded['scenario_id']}", headers=h)).json()
    assert detail["events"][0]["key"] == "initial_briefing"

    body = copy.deepcopy(GREY_SIGNAL)
    body["name"] = "Training Variant"
    body["difficulty"] = "ADVANCED"
    created = await client.post("/api/v1/scenarios", json=body, headers=h)
    assert created.status_code == 201
    sid = created.json()["id"]

    body["description"] = "Updated description"
    body["events"] = body["events"][:3]
    updated = await client.put(f"/api/v1/scenarios/{sid}", json=body, headers=h)
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated description"
    assert len(updated.json()["events"]) == 3

    dup = await client.post(f"/api/v1/scenarios/{sid}/duplicate", headers=h)
    assert dup.status_code == 201 and dup.json()["name"].endswith("(copy)")

    assert (await client.delete(f"/api/v1/scenarios/{sid}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/scenarios/{sid}", headers=h)).status_code == 404


async def test_room_snapshot_is_immune_to_template_edits(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    h = await login(client, "instructor")
    room = (
        await client.post("/api/v1/rooms", json={"scenario_id": seeded["scenario_id"]}, headers=h)
    ).json()
    body = copy.deepcopy(GREY_SIGNAL)
    body["events"] = body["events"][:2]
    await client.put(f"/api/v1/scenarios/{seeded['scenario_id']}", json=body, headers=h)
    state = (await client.get(f"/api/v1/rooms/{room['id']}/state", headers=h)).json()
    assert len([t for t in state["timeline"] if t["kind"] == "EVENT"]) == len(GREY_SIGNAL["events"])
