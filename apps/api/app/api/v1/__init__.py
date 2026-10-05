from fastapi import APIRouter

from app.api.v1 import aar, admin, analytics, auth, comms, controls, live, rooms, scenarios

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(scenarios.router)
api_router.include_router(rooms.router)
api_router.include_router(live.router)
api_router.include_router(controls.router)
api_router.include_router(comms.router)
api_router.include_router(aar.router)
api_router.include_router(analytics.router)
