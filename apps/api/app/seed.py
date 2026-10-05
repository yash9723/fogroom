"""Seed demo accounts and the Operation Grey Signal scenario.

Idempotent: re-running updates the demo users' passwords/roles and replaces the Grey
Signal template definition (existing rooms keep their frozen snapshots).

    python -m app.seed
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import db
from app.models.enums import UserRole
from app.models.scenario import ScenarioTemplate
from app.models.user import User
from app.scenario.library.grey_signal import GREY_SIGNAL
from app.scenario.loader import apply_scenario, get_scenario, replace_scenario
from app.schemas.scenario import ScenarioCreate

logger = logging.getLogger("fogroom.seed")

DEMO_USERS = [
    ("admin@fogroom.demo", "Platform Admin", UserRole.ADMIN),
    ("instructor@fogroom.demo", "Instructor Rao", UserRole.INSTRUCTOR),
    ("alpha@fogroom.demo", "Trainee Alpha", UserRole.TRAINEE),
    ("bravo@fogroom.demo", "Trainee Bravo", UserRole.TRAINEE),
    ("charlie@fogroom.demo", "Trainee Charlie", UserRole.TRAINEE),
]


async def seed() -> None:
    async with db.sessionmaker() as session:
        password_hash = hash_password(settings.demo_password)
        instructor: User | None = None
        for email, name, role in DEMO_USERS:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email, display_name=name, role=role.value, password_hash=password_hash
                )
                session.add(user)
            else:
                user.password_hash = password_hash
                user.role = role.value
                user.is_active = True
            if role == UserRole.INSTRUCTOR:
                instructor = user
        await session.flush()

        data = ScenarioCreate.model_validate(GREY_SIGNAL)
        existing = await session.scalar(
            select(ScenarioTemplate).where(ScenarioTemplate.name == data.name)
        )
        if existing is None:
            scenario = apply_scenario(
                ScenarioTemplate(created_by=instructor.id if instructor else None), data
            )
            session.add(scenario)
            action = "created"
        else:
            scenario = await get_scenario(session, existing.id)
            await replace_scenario(session, scenario, data)
            action = "updated"
        await session.commit()
        print(f"Seeded {len(DEMO_USERS)} demo users; scenario '{data.name}' {action}.")  # noqa: T201
        print("Demo password comes from DEMO_PASSWORD (see .env).")  # noqa: T201
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
