import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.workspaces.schemas import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.workspaces.service import (
    create_workspace,
    delete_workspace,
    get_workspace,
    get_workspaces,
    update_workspace,
)


router = APIRouter(
    prefix="/api/v1/workspaces",
    tags=["Workspaces"],
)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_workspace(
        db,
        current_user.id,
        data,
    )


@router.get(
    "",
    response_model=list[WorkspaceResponse],
)
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_workspaces(
        db,
        current_user.id,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def get(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await get_workspace(
        db,
        workspace_id,
        current_user.id,
    )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return workspace


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def update(
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await get_workspace(
        db,
        workspace_id,
        current_user.id,
    )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return await update_workspace(
        db,
        workspace,
        data,
    )


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await get_workspace(
        db,
        workspace_id,
        current_user.id,
    )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    await delete_workspace(db, workspace)