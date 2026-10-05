from typing import Any

from fastapi import APIRouter

from app.analytics.service import dashboard, overview
from app.auth.deps import InstructorUser, SessionDep

router = APIRouter(tags=["analytics"])


@router.get("/dashboard", summary="Instructor dashboard summary")
async def get_dashboard(user: InstructorUser, session: SessionDep) -> dict[str, Any]:
    return await dashboard(session, user)


@router.get("/analytics/overview", summary="Analytics across completed exercises")
async def get_overview(user: InstructorUser, session: SessionDep) -> dict[str, Any]:
    return await overview(session, user)
