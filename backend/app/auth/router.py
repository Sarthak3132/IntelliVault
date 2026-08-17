import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserResponse

from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RefreshRequest,
)
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from app.auth.service import login_user, register_user
from app.core.config import settings
from app.db.database import get_db
from app.db.models.refresh_session import RefreshSession
from app.db.models.user import User


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user, access_token, refresh_token = await register_user(
            db,
            request.email,
            request.password,
        )

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=AuthResponse,
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user, access_token, refresh_token = await login_user(
            db,
            request.email,
            request.password,
        )

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_refresh_token(request.refresh_token)

    result = await db.execute(
        select(RefreshSession).where(
            RefreshSession.token_hash == token_hash,
            RefreshSession.revoked == False,
        )
    )

    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    if session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=401,
            detail="Refresh token expired",
        )

    # Rotate old refresh token
    session.revoked = True

    new_refresh_token = create_refresh_token()

    new_session = RefreshSession(
        user_id=session.user_id,
        token_hash=hash_refresh_token(new_refresh_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )

    db.add(new_session)

    result = await db.execute(
        select(User).where(User.id == session.user_id)
    )

    user = result.scalar_one()

    new_access_token = create_access_token(str(user.id))

    await db.commit()

    return {
        "user": user,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
    }

@router.post("/logout")
async def logout(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_refresh_token(request.refresh_token)

    result = await db.execute(
        select(RefreshSession).where(
            RefreshSession.token_hash == token_hash
        )
    )

    session = result.scalar_one_or_none()

    if session:
        session.revoked = True
        await db.commit()

    return {"message": "Logged out successfully"}