"""Authentication: credential checks, token issue and refresh-token rotation."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenPair, UserOut

logger = logging.getLogger("fogroom.auth")

# Verifying against a dummy hash for unknown emails keeps response timing uniform.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password-1")


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    display_name: str,
    role: UserRole = UserRole.TRAINEE,
) -> User:
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        role=role.value,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise conflict("EMAIL_TAKEN", "An account with this email already exists.") from exc
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise unauthorized("Invalid email or password.", "INVALID_CREDENTIALS")
    if not verify_password(password, user.password_hash):
        raise unauthorized("Invalid email or password.", "INVALID_CREDENTIALS")
    if not user.is_active:
        raise unauthorized("This account is disabled.", "ACCOUNT_DISABLED")
    return user


async def issue_tokens(
    session: AsyncSession, user: User, family_id: uuid.UUID | None = None
) -> TokenPair:
    access, expires_in = create_access_token(user.id, user.role)
    raw_refresh = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=family_id or uuid.uuid4(),
            expires_at=refresh_expiry(),
        )
    )
    await session.flush()
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


async def rotate_refresh_token(session: AsyncSession, raw_token: str) -> TokenPair:
    token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        .with_for_update()
    )
    if token is None:
        raise unauthorized("Invalid refresh token.", "REFRESH_INVALID")
    now = datetime.now(UTC)
    if token.revoked_at is not None:
        # A rotated token was replayed - assume theft and revoke the whole family.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
        logger.warning("Refresh token reuse detected for user %s; family revoked", token.user_id)
        raise unauthorized("Refresh token reuse detected. Please sign in again.", "REFRESH_REUSED")
    if token.expires_at <= now:
        raise unauthorized("Refresh token expired. Please sign in again.", "REFRESH_EXPIRED")
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise unauthorized("Account unavailable.", "ACCOUNT_DISABLED")
    token.revoked_at = now
    return await issue_tokens(session, user, family_id=token.family_id)


async def revoke_refresh_token(session: AsyncSession, raw_token: str) -> None:
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if token is None:
        return
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
