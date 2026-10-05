"""Test configuration.

Tests run against a real PostgreSQL database (`fogroom_test`) and Redis DB 15 so that
constraints, JSONB behaviour, row locks and pub/sub are exercised for real.
Environment overrides must happen before any `app.*` import.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://fogroom:fogroom@localhost:5432/fogroom_test"
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["DB_NULL_POOL"] = "true"
os.environ["ENGINE_AUTORUN"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["LOGIN_RATE_LIMIT"] = "50"

import asyncio  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.redis import redis_state  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ScenarioTemplate, User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.scenario.library.grey_signal import GREY_SIGNAL  # noqa: E402
from app.scenario.loader import apply_scenario  # noqa: E402
from app.schemas.scenario import ScenarioCreate  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "Test-pass-123"
_HASH: dict[str, str] = {}

USERS = {
    "admin": ("admin@fogroom.demo", "Platform Admin", UserRole.ADMIN),
    "instructor": ("instructor@fogroom.demo", "Instructor Rao", UserRole.INSTRUCTOR),
    "instructor2": ("other.instructor@fogroom.demo", "Instructor Two", UserRole.INSTRUCTOR),
    "alpha": ("alpha@fogroom.demo", "Trainee Alpha", UserRole.TRAINEE),
    "bravo": ("bravo@fogroom.demo", "Trainee Bravo", UserRole.TRAINEE),
    "charlie": ("charlie@fogroom.demo", "Trainee Charlie", UserRole.TRAINEE),
    "delta": ("delta@fogroom.demo", "Trainee Delta", UserRole.TRAINEE),
}


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Rebuild the test schema from Alembic migrations once per session."""
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with db.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    redis_state.client = None
    await redis_state.get().flushdb()
    yield
    await redis_state.close()


@pytest.fixture
async def seeded() -> dict[str, Any]:
    async with db.sessionmaker() as session:
        if "h" not in _HASH:
            _HASH["h"] = hash_password(PASSWORD)
        users = {}
        for key, (email, name, role) in USERS.items():
            user = User(email=email, display_name=name, role=role.value, password_hash=_HASH["h"])
            session.add(user)
            users[key] = user
        await session.flush()
        scenario = apply_scenario(
            ScenarioTemplate(created_by=users["instructor"].id),
            ScenarioCreate.model_validate(GREY_SIGNAL),
        )
        session.add(scenario)
        await session.commit()
        return {"users": {k: str(u.id) for k, u in users.items()}, "scenario_id": str(scenario.id)}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client: AsyncClient, persona: str) -> dict[str, str]:
    email = USERS[persona][0]
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def get_user(email: str) -> User:
    async with db.sessionmaker() as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        return user


class Exercise:
    """Helper that drives a Grey Signal exercise through the public API."""

    def __init__(self, client: AsyncClient) -> None:
        self.client = client
        self.h: dict[str, dict[str, str]] = {}
        self.room_id = ""
        self.pid: dict[str, str] = {}

    async def setup(self, start: bool = True) -> "Exercise":
        for persona in ("instructor", "alpha", "bravo", "charlie"):
            self.h[persona] = await login(self.client, persona)
        resp = await self.client.post("/api/v1/demo/launch", json={}, headers=self.h["instructor"])
        assert resp.status_code == 201, resp.text
        room = resp.json()
        self.room_id = room["id"]
        self.code = room["room_code"]
        for persona in ("alpha", "bravo", "charlie"):
            r = await self.client.post(
                "/api/v1/rooms/join", json={"room_code": self.code}, headers=self.h[persona]
            )
            assert r.status_code == 200, r.text
            self.pid[persona] = r.json()["participant_id"]
        if start:
            r = await self.client.post(
                f"/api/v1/rooms/{self.room_id}/start", headers=self.h["instructor"]
            )
            assert r.status_code == 200, r.text
        return self

    def url(self, path: str) -> str:
        return f"/api/v1/rooms/{self.room_id}{path}"

    async def advance(self, to: float) -> None:
        r = await self.client.post(
            self.url("/clock/advance"), json={"to_sim_seconds": to}, headers=self.h["instructor"]
        )
        assert r.status_code == 200, r.text

    async def me(self, persona: str) -> dict[str, Any]:
        r = await self.client.get(self.url("/me"), headers=self.h[persona])
        assert r.status_code == 200, r.text
        return r.json()

    async def titles(self, persona: str) -> list[str]:
        return [m["title"] for m in (await self.me(persona))["messages"]]

    async def info_state(self, persona: str, t: float) -> dict[str, Any]:
        r = await self.client.get(
            self.url(f"/participants/{self.pid[persona]}/information-state"),
            params={"timestamp": t},
            headers=self.h["instructor"],
        )
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
async def exercise(client: AsyncClient, seeded: dict[str, Any]) -> Exercise:
    return await Exercise(client).setup()


def run(coro: Any) -> Any:
    """Run a coroutine from a synchronous test (e.g. alongside Starlette's TestClient)."""
    return asyncio.run(coro)


__all__ = ["PASSWORD", "Exercise", "login", "get_user", "run"]
