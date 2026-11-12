from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.embedding import ChunkEmbedding
from app.models.transcript import TranscriptChunk


def replace_chunks(
    db: Session,
    *,
    video_id: int,
    chunks: Iterable[dict[str, float | str]],
) -> list[TranscriptChunk]:
    db.execute(delete(TranscriptChunk).where(TranscriptChunk.video_id == video_id))
    records = [
        TranscriptChunk(
            video_id=video_id,
            text=str(chunk["text"]),
            start_time=float(chunk["start_time"]),
            end_time=float(chunk["end_time"]),
        )
        for chunk in chunks
    ]
    db.add_all(records)
    db.flush()
    return records


def save_embeddings(
    db: Session,
    *,
    chunks: list[TranscriptChunk],
    vectors: list[list[float]],
    model_name: str,
) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("Chunk and embedding counts do not match")
    db.add_all(
        [
            ChunkEmbedding(chunk_id=chunk.chunk_id, embedding=vector, model_name=model_name)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
    )
    db.flush()


def list_chunks(db: Session, video_id: int) -> list[TranscriptChunk]:
    return list(
        db.scalars(
            select(TranscriptChunk)
            .where(TranscriptChunk.video_id == video_id)
            .order_by(TranscriptChunk.start_time)
        )
    )
