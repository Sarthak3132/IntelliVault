import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.config import settings
from app.db.models.refresh_session import RefreshSession
from app.db.models.user import User


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
):
    result = await db.execute(
        select(User).where(User.email == email)
    )

    if result.scalar_one_or_none():
        raise ValueError("Email already registered")

    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
    )

    db.add(user)
    await db.flush()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token()

    session = RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )

    db.add(session)

    await db.commit()
    await db.refresh(user)

    return user, access_token, refresh_token


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
):
    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if not user or not verify_password(
        password,
        user.password_hash,
    ):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token()

    session = RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )

    db.add(session)
    await db.commit()

    return user, access_token, refresh_token