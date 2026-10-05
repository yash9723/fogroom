import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.auth.deps import AdminUser, SessionDep
from app.core.errors import AppError, not_found
from app.models.enums import ActorType
from app.models.user import User
from app.schemas.auth import AdminUserUpdate, UserOut
from app.services.audit import record_event

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut], summary="List all users (admin)")
async def list_users(_: AdminUser, session: SessionDep) -> list[User]:
    return list((await session.scalars(select(User).order_by(User.created_at))).all())


@router.patch(
    "/users/{user_id}", response_model=UserOut, summary="Change role / active flag (admin)"
)
async def update_user(
    user_id: uuid.UUID, body: AdminUserUpdate, admin: AdminUser, session: SessionDep
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("USER_NOT_FOUND", "User not found.")
    if user.id == admin.id and (body.role is not None or body.is_active is False):
        raise AppError(
            "SELF_MODIFICATION", "Admins cannot change their own role or disable themselves.", 422
        )
    changes: dict[str, object] = {}
    if body.role is not None:
        changes["role"] = {"from": user.role, "to": body.role.value}
        user.role = body.role.value
    if body.is_active is not None:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
    await record_event(
        session,
        None,
        "admin.user_updated",
        {"user_id": str(user.id), "changes": changes},
        actor_id=admin.id,
        actor_type=ActorType.USER,
    )
    await session.commit()
    await session.refresh(user)
    return user
