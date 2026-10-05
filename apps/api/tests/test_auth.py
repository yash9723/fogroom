from typing import Any

from httpx import AsyncClient

from app.core.config import settings
from tests.conftest import PASSWORD, login


async def test_register_creates_trainee_and_returns_tokens(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "New.User@Example.com", "password": "secret123", "display_name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "TRAINEE"
    assert body["user"]["email"] == "new.user@example.com"
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200


async def test_register_rejects_weak_password_and_duplicates(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    weak = await client.post(
        "/api/v1/auth/register", json={"email": "a@b.co", "password": "short", "display_name": "x"}
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "VALIDATION_ERROR"
    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": "alpha@fogroom.demo", "password": "secret123", "display_name": "Dup"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_login_wrong_password_uses_error_envelope(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "alpha@fogroom.demo", "password": "nope-nope1"}
    )
    assert resp.status_code == 401
    assert resp.json() == {
        "error": {
            "code": "INVALID_CREDENTIALS",
            "message": "Invalid email or password.",
            "details": {},
        }
    }


async def test_protected_route_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    bad = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "TOKEN_INVALID"


async def test_refresh_rotation_and_reuse_detection(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    first = (
        await client.post(
            "/api/v1/auth/login", json={"email": "bravo@fogroom.demo", "password": PASSWORD}
        )
    ).json()
    second = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert second.status_code == 200
    rotated = second.json()["refresh_token"]
    assert rotated != first["refresh_token"]

    replay = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "REFRESH_REUSED"
    # The whole family is revoked after reuse.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated})
    assert after.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient, seeded: dict[str, Any]) -> None:
    tokens = (
        await client.post(
            "/api/v1/auth/login", json={"email": "bravo@fogroom.demo", "password": PASSWORD}
        )
    ).json()
    assert (
        await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 204
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 401


async def test_login_rate_limit(
    client: AsyncClient, seeded: dict[str, Any], monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "login_rate_limit", 3)
    for _ in range(3):
        r = await client.post(
            "/api/v1/auth/login", json={"email": "alpha@fogroom.demo", "password": "wrong-pass1"}
        )
        assert r.status_code == 401
    blocked = await client.post(
        "/api/v1/auth/login", json={"email": "alpha@fogroom.demo", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


async def test_demo_login_issues_real_tokens(client: AsyncClient, seeded: dict[str, Any]) -> None:
    resp = await client.post("/api/v1/auth/demo-login", json={"persona": "instructor"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "INSTRUCTOR"


async def test_demo_login_disabled_outside_demo_mode(
    client: AsyncClient, seeded: dict[str, Any], monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "demo_mode", False)
    resp = await client.post("/api/v1/auth/demo-login", json={"persona": "alpha"})
    assert resp.status_code == 404


async def test_admin_can_promote_user_and_trainee_cannot(
    client: AsyncClient, seeded: dict[str, Any]
) -> None:
    admin = await login(client, "admin")
    trainee = await login(client, "alpha")
    target = seeded["users"]["delta"]
    assert (await client.get("/api/v1/admin/users", headers=trainee)).status_code == 403
    resp = await client.patch(
        f"/api/v1/admin/users/{target}", json={"role": "INSTRUCTOR"}, headers=admin
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "INSTRUCTOR"
