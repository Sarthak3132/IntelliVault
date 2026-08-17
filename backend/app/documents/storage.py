import uuid
from pathlib import Path


STORAGE_ROOT = Path("storage")


def get_document_directory(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Path:

    directory = (
        STORAGE_ROOT
        / "workspaces"
        / str(workspace_id)
        / str(document_id)
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


async def save_document_file(
    file,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Path:

    directory = get_document_directory(
        workspace_id,
        document_id,
    )

    file_path = directory / "original"

    contents = await file.read()

    file_path.write_bytes(contents)

    return file_path