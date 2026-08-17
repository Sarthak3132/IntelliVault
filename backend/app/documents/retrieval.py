from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk


SIMILARITY_THRESHOLD = 0.60


async def search_similar_chunks(
    db: AsyncSession,
    document_id,
    query_embedding: list[float],
    limit: int = 5,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
):
    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    similarity = (1 - distance).label("similarity")

    result = await db.execute(
        select(
            DocumentChunk,
            distance.label("distance"),
            similarity,
        )
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.embedding.is_not(None),
            similarity >= similarity_threshold,
        )
        .order_by(distance)
        .limit(limit)
    )

    rows = result.all()

    return [
        {
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "distance": float(distance_value),
            "similarity": float(similarity_value),
        }
        for chunk, distance_value, similarity_value in rows
    ]


async def search_workspace_chunks(
    db: AsyncSession,
    workspace_id,
    query_embedding: list[float],
    limit: int = 5,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
):
    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    similarity = (1 - distance).label("similarity")

    result = await db.execute(
        select(
            DocumentChunk,
            Document,
            distance.label("distance"),
            similarity,
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            Document.workspace_id == workspace_id,
            DocumentChunk.embedding.is_not(None),
            similarity >= similarity_threshold,
        )
        .order_by(distance)
        .limit(limit)
    )

    rows = result.all()

    return [
        {
            "document_id": str(document.id),
            "filename": document.filename,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "distance": float(distance_value),
            "similarity": float(similarity_value),
        }
        for (
            chunk,
            document,
            distance_value,
            similarity_value,
        ) in rows
    ]