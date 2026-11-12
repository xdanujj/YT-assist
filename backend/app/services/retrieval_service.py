"""Vector retrieval with a timestamp proximity boost."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.embedding import ChunkEmbedding
from app.models.transcript import TranscriptChunk


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    text: str
    start_time: float
    end_time: float
    semantic_score: float
    proximity_score: float
    score: float


def timestamp_proximity(start_time: float, end_time: float, current_time: float) -> float:
    """Return a 0..1 score, with a ~5 minute decay away from the playhead."""
    if start_time <= current_time <= end_time:
        return 1.0
    distance = min(abs(current_time - start_time), abs(current_time - end_time))
    return exp(-distance / 300)


def rerank_candidates(
    candidates: list[tuple[TranscriptChunk, float]], current_time: float
) -> list[RetrievedChunk]:
    settings = get_settings()
    proximity_weight = settings.proximity_weight
    results: list[RetrievedChunk] = []
    for chunk, distance in candidates:
        semantic_score = max(0.0, 1.0 - float(distance))
        proximity_score = timestamp_proximity(chunk.start_time, chunk.end_time, current_time)
        score = semantic_score * (1 - proximity_weight) + proximity_score * proximity_weight
        results.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                start_time=chunk.start_time,
                end_time=chunk.end_time,
                semantic_score=semantic_score,
                proximity_score=proximity_score,
                score=score,
            )
        )
    return sorted(results, key=lambda item: item.score, reverse=True)[: settings.retrieval_limit]


def retrieve(
    db: Session, *, video_id: int, query_embedding: list[float], current_time: float
) -> list[RetrievedChunk]:
    settings = get_settings()
    distance = ChunkEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    rows = db.execute(
        select(TranscriptChunk, distance)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == TranscriptChunk.chunk_id)
        .where(TranscriptChunk.video_id == video_id)
        .order_by(distance)
        .limit(settings.retrieval_candidates)
    ).all()
    return rerank_candidates([(chunk, float(value)) for chunk, value in rows], current_time)
