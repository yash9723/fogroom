"""Real-time path: WebSocket auth handshake and per-viewer filtered fan-out via Redis."""

import time
from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from tests.conftest import PASSWORD


def _login(tc: TestClient, email: str) -> str:
    resp = tc.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


def test_websocket_requires_auth(seeded: dict[str, Any]) -> None:
    with (
        TestClient(app) as tc,
        tc.websocket_connect("/ws/rooms/00000000-0000-0000-0000-000000000000") as ws,
    ):
        ws.send_json({"type": "auth", "token": "garbage"})
        assert ws.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401


def test_websocket_delivers_filtered_events(seeded: dict[str, Any]) -> None:
    with TestClient(app) as tc:
        inst = {"Authorization": f"Bearer {_login(tc, 'instructor@fogroom.demo')}"}
        alpha_token = _login(tc, "alpha@fogroom.demo")
        bravo = {"Authorization": f"Bearer {_login(tc, 'bravo@fogroom.demo')}"}
        room = tc.post("/api/v1/demo/launch", json={}, headers=inst).json()
        alpha_join = tc.post(
            "/api/v1/rooms/join",
            json={"room_code": room["room_code"]},
            headers={"Authorization": f"Bearer {alpha_token}"},
        ).json()
        tc.post("/api/v1/rooms/join", json={"room_code": room["room_code"]}, headers=bravo)
        assert tc.post(f"/api/v1/rooms/{room['id']}/start", headers=inst).status_code == 200

        with tc.websocket_connect(f"/ws/rooms/{room['id']}") as ws:
            ws.send_json({"type": "auth", "token": alpha_token})
            hello = ws.receive_json()
            assert hello["type"] == "hello" and hello["viewer"] == "TRAINEE"
            assert hello["participant_id"] == alpha_join["participant_id"]

            ws.send_json({"type": "ping"})
            resp = tc.post(
                f"/api/v1/rooms/{room['id']}/notices",
                json={
                    "title": "Alpha only",
                    "content": "Check the bridge.",
                    "target_participant_ids": [alpha_join["participant_id"]],
                },
                headers=inst,
            )
            assert resp.status_code == 201

            seen: list[dict[str, Any]] = []
            for _ in range(20):
                frame = ws.receive_json()
                if frame["type"] != "event":
                    continue
                seen.append(frame["event"])
                if frame["event"]["event_type"] == "message.delivered":
                    break
            delivered = [e for e in seen if e["event_type"] == "message.delivered"]
            assert delivered and delivered[0]["payload"]["title"] == "Alpha only"
            assert not any(
                e["event_type"] in ("message.created", "delivery.completed") for e in seen
            )
            assert all("targets" not in e for e in seen)

        # Disconnect is recorded asynchronously once the server notices the closed socket.
        status = "CONNECTED"
        for _ in range(40):
            participants = tc.get(f"/api/v1/rooms/{room['id']}/participants", headers=inst).json()
            status = next(p for p in participants if p["callsign"] == "ALPHA")["connection_status"]
            if status == "DISCONNECTED":
                break
            time.sleep(0.05)
        assert status == "DISCONNECTED"
