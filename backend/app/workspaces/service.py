import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspace import Workspace
from app.workspaces.schemas import WorkspaceCreate, WorkspaceUpdate


async def create_workspace(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: WorkspaceCreate,
) -> Workspace:

    workspace = Workspace(
        user_id=user_id,
        name=data.name,
        description=data.description,
    )

    db.add(workspace)

    await db.commit()
    await db.refresh(workspace)

    return workspace


async def get_workspaces(
    db: AsyncSession,
    user_id: uuid.UUID,
):
    result = await db.execute(
        select(Workspace)
        .where(Workspace.user_id == user_id)
        .order_by(Workspace.created_at.desc())
    )

    return result.scalars().all()


async def get_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
):
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def update_workspace(
    db: AsyncSession,
    workspace: Workspace,
    data: WorkspaceUpdate,
):
    if data.name is not None:
        workspace.name = data.name

    if data.description is not None:
        workspace.description = data.description

    await db.commit()
    await db.refresh(workspace)

    return workspace


async def delete_workspace(
    db: AsyncSession,
    workspace: Workspace,
):
    await db.delete(workspace)
    await db.commit()