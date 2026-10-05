import logging

from fastapi import APIRouter, Request, status

from app.auth.deps import CurrentUser, SessionDep
from app.auth.service import (
    authenticate,
    issue_tokens,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.core.config import settings
from app.core.errors import AppError, not_found
from app.core.ratelimit import check_login_rate, reset_login_rate
from app.models.enums import ActorType
from app.models.user import User
from app.schemas.auth import (
    DemoLoginIn,
    LoginIn,
    ProfileUpdate,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)
from app.services.audit import record_event

logger = logging.getLogger("fogroom.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_EMAILS = {
    "instructor": "instructor@fogroom.demo",
    "alpha": "alpha@fogroom.demo",
    "bravo": "bravo@fogroom.demo",
    "charlie": "charlie@fogroom.demo",
    "admin": "admin@fogroom.demo",
}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Create a trainee account",
)
async def register(body: RegisterIn, session: SessionDep) -> TokenPair:
    """Self-registration always creates a TRAINEE. Instructors are promoted by an admin."""
    user = await register_user(session, body.email, body.password, body.display_name)
    tokens = await issue_tokens(session, user)
    await record_event(
        session,
        None,
        "auth.registered",
        {"user_id": str(user.id)},
        actor_id=user.id,
        actor_type=ActorType.USER,
    )
    await session.commit()
    logger.info("User registered id=%s", user.id)
    return tokens


@router.post("/login", response_model=TokenPair, summary="Sign in with email and password")
async def login(body: LoginIn, request: Request, session: SessionDep) -> TokenPair:
    ip = _client_ip(request)
    await check_login_rate(ip, body.email)
    user = await authenticate(session, body.email, body.password)
    tokens = await issue_tokens(session, user)
    await record_event(
        session,
        None,
        "auth.login",
        {"user_id": str(user.id)},
        actor_id=user.id,
        actor_type=ActorType.USER,
    )
    await session.commit()
    await reset_login_rate(ip, body.email)
    logger.info("User login id=%s role=%s", user.id, user.role)
    return tokens


@router.post(
    "/demo-login", response_model=TokenPair, summary="One-click login for seeded demo personas"
)
async def demo_login(body: DemoLoginIn, session: SessionDep) -> TokenPair:
    """Only available when DEMO_MODE=true. Issues real tokens for the seeded demo accounts."""
    if not settings.demo_mode:
        raise not_found("DEMO_DISABLED", "Demo mode is disabled on this server.")
    from sqlalchemy import select

    user = await session.scalar(select(User).where(User.email == DEMO_EMAILS[body.persona]))
    if user is None:
        raise AppError("DEMO_NOT_SEEDED", "Demo accounts are missing - run the seed command.", 409)
    tokens = await issue_tokens(session, user)
    await record_event(
        session,
        None,
        "auth.demo_login",
        {"user_id": str(user.id), "persona": body.persona},
        actor_id=user.id,
        actor_type=ActorType.USER,
    )
    await session.commit()
    logger.info("Demo login persona=%s", body.persona)
    return tokens


@router.post("/refresh", response_model=TokenPair, summary="Rotate a refresh token")
async def refresh(body: RefreshIn, session: SessionDep) -> TokenPair:
    tokens = await rotate_refresh_token(session, body.refresh_token)
    await session.commit()
    return tokens


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token family"
)
async def logout(body: RefreshIn, session: SessionDep) -> None:
    await revoke_refresh_token(session, body.refresh_token)
    await session.commit()


@router.get("/me", response_model=UserOut, summary="Current user")
async def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut, summary="Update own profile")
async def update_me(body: ProfileUpdate, user: CurrentUser, session: SessionDep) -> User:
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/demo-config", summary="Whether one-click demo logins are enabled")
async def demo_config() -> dict[str, object]:
    return {
        "demo_mode": settings.demo_mode,
        "personas": list(DEMO_EMAILS) if settings.demo_mode else [],
    }
