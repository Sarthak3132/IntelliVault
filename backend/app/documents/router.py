import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user

from app.db.database import get_db
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.user import User
from app.db.models.workspace import Workspace

from app.ai.generation import generate_answer
from app.ai.embeddings import generate_embeddings

from app.documents.retrieval import (
    search_similar_chunks,
    search_workspace_chunks,
)
from app.documents.chunker import chunk_text
from app.documents.service import extract_text

from pathlib import Path


router = APIRouter(
    prefix="/api/v1/workspaces",
    tags=["Documents"],
)


@router.post(
    "/{workspace_id}/documents",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------
    # 1. Verify workspace ownership
    # --------------------------------

    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )

    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    # --------------------------------
    # 2. Read uploaded file
    # --------------------------------

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="File is empty",
        )

    filename = file.filename or "unknown"

    # --------------------------------
    # 3. Extract text
    # --------------------------------

    try:
        text = extract_text(
            filename,
            contents,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Document contains no extractable text",
        )

    # --------------------------------
    # 4. Create document
    # --------------------------------

    document = Document(
        workspace_id=workspace_id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(contents),
        extracted_characters=len(text),
        status="processing",
    )

    db.add(document)

    await db.flush()

    # --------------------------------
    # 5. Save original file
    # --------------------------------

    directory = (
        Path("storage")
        / "workspaces"
        / str(workspace_id)
        / str(document.id)
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = directory / filename

    file_path.write_bytes(contents)
    # --------------------------------
    # 6. Chunk text
    # --------------------------------

    chunks = chunk_text(text)

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Document could not be divided into chunks",
        )

    # --------------------------------
    # 7. Generate embeddings
    # --------------------------------

    try:
        embeddings = await generate_embeddings(chunks)

        if len(embeddings) != len(chunks):
            document.status = "failed"
            await db.commit()

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Embedding count mismatch: "
                    f"{len(chunks)} chunks, "
                    f"{len(embeddings)} embeddings"
                ),
    )

    except Exception:
        document.status = "failed"
        await db.commit()

        raise HTTPException(
            status_code=502,
            detail="Failed to generate document embeddings",
        )

    # --------------------------------
    # 8. Save chunks + embeddings
    # --------------------------------

    for index, (content, embedding) in enumerate(
        zip(chunks, embeddings)
    ):
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=content,
            embedding=embedding,
        )

        db.add(chunk)

    # --------------------------------
    # 9. Mark processing complete
    # --------------------------------

    document.status = "ready"

    await db.commit()

    await db.refresh(document)

    return {
        "id": str(document.id),
        "filename": document.filename,
        "size_bytes": document.size_bytes,
        "characters": document.extracted_characters,
        "chunks": len(chunks),
        "status": document.status,
    }

@router.get("/{workspace_id}/documents/{document_id}/search")
async def search_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    query: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify document belongs to user's workspace
    result = await db.execute(
        select(Document)
        .join(
            Workspace,
            Workspace.id == Document.workspace_id,
        )
        .where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )

    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # Convert question into embedding
    embeddings = await generate_embeddings([query])
    query_embedding = embeddings[0]

    # Retrieve relevant chunks
    chunks = await search_similar_chunks(
        db=db,
        document_id=document_id,
        query_embedding=query_embedding,
        limit=5,
    )

    return {
    "query": query,
    "results": chunks,
    }
@router.get(
    "/{workspace_id}/documents/{document_id}/ask"
)
async def ask_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    query: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------
    # 1. Verify document ownership
    # --------------------------------

    result = await db.execute(
        select(Document)
        .join(
            Workspace,
            Workspace.id == Document.workspace_id,
        )
        .where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )

    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # --------------------------------
    # 2. Validate query
    # --------------------------------

    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    # --------------------------------
    # 3. Generate query embedding
    # --------------------------------

    try:
        embeddings = await generate_embeddings(
            [query]
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate query embedding",
        )

    if not embeddings:
        raise HTTPException(
            status_code=502,
            detail="No query embedding generated",
        )

    query_embedding = embeddings[0]

    # --------------------------------
    # 4. Retrieve relevant chunks
    # --------------------------------

    try:
        chunks = await search_similar_chunks(
            db=db,
            document_id=document_id,
            query_embedding=query_embedding,
            limit=5,
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve document context",
        )

    if not chunks:
        return {
            "query": query,
            "answer": (
                "I couldn't find relevant information "
                "in the provided document."
            ),
            "sources": [],
        }

    # --------------------------------
    # 5. Build context
    # --------------------------------

    context = "\n\n".join(
        chunk["content"]
        for chunk in chunks
    )

    # --------------------------------
    # 6. Generate answer
    # --------------------------------

    try:
        answer = await generate_answer(
            question=query,
            context=context,
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate answer",
        )

    # --------------------------------
    # 7. Return answer + sources
    # --------------------------------

    return {
        "query": query,
        "answer": answer,
        "sources": [
            {
                "chunk_index": chunk["chunk_index"],
                "similarity": chunk["similarity"],
            }
            for chunk in chunks
        ],
    }

@router.get(
    "/{workspace_id}/ask"
)
async def ask_workspace(
    workspace_id: uuid.UUID,
    query: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------
    # 1. Verify workspace ownership
    # --------------------------------

    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )

    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    # --------------------------------
    # 2. Validate query
    # --------------------------------

    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    # --------------------------------
    # 3. Generate query embedding
    # --------------------------------

    try:
        embeddings = await generate_embeddings(
            [query]
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate query embedding",
        )

    if not embeddings:
        raise HTTPException(
            status_code=502,
            detail="No query embedding generated",
        )

    query_embedding = embeddings[0]

    # --------------------------------
    # 4. Search entire workspace
    # --------------------------------

    try:
        chunks = await search_workspace_chunks(
            db=db,
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            limit=5,
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve workspace context",
        )

    # --------------------------------
    # 5. No relevant information
    # --------------------------------

    if not chunks:
        return {
            "query": query,
            "answer": (
                "I couldn't find relevant information "
                "in the provided workspace."
            ),
            "sources": [],
        }

    # --------------------------------
    # 6. Build context
    # --------------------------------

    context = "\n\n".join(
        (
            f"Source: {chunk['filename']}\n"
            f"Content:\n{chunk['content']}"
        )
        for chunk in chunks
    )

    # --------------------------------
    # 7. Generate answer
    # --------------------------------

    try:
        answer = await generate_answer(
            question=query,
            context=context,
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate answer",
        )

    # --------------------------------
    # 8. Return answer + sources
    # --------------------------------

    return {
        "query": query,
        "answer": answer,
        "sources": [
            {
                "document_id": chunk["document_id"],
                "filename": chunk["filename"],
                "chunk_index": chunk["chunk_index"],
                "similarity": chunk["similarity"],
            }
            for chunk in chunks
        ],
    }