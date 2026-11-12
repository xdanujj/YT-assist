"""Database repository for video, transcript, chunk, and chat operations."""

from __future__ import annotations

import logging
import uuid
from typing import Any, List, Optional, Sequence, Tuple

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.chunking import Chunk as CoreChunk
from app.db.models import ChatMessage, Chunk, TranscriptSegment, Video
from app.providers.base import TranscriptSegment as ProviderSegment

logger = logging.getLogger(__name__)


def get_engine_and_session(database_url: str):
    """Create and return an async SQLAlchemy engine and session factory."""
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    return engine, session_factory


class VideoRepository:
    """Handles all database persistence operations."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_video(self, video_id: str) -> Optional[Video]:
        """Fetch video by YouTube video_id."""
        async with self.session_factory() as session:
            stmt = select(Video).where(Video.video_id == video_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_or_create_video(self, video_id: str) -> Video:
        """Fetch existing video or create a new one with 'pending' status."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = select(Video).where(Video.video_id == video_id)
                result = await session.execute(stmt)
                video = result.scalar_one_or_none()
                if video is not None:
                    return video

                video = Video(
                    video_id=video_id,
                    status="pending",
                )
                session.add(video)
            # Fetch again to refresh in non-expired state
            await session.refresh(video)
            return video

    async def update_video_status(
        self, video_id: str, status: str, error: Optional[str] = None
    ) -> Optional[Video]:
        """Update video status and optional error message."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = select(Video).where(Video.video_id == video_id)
                result = await session.execute(stmt)
                video = result.scalar_one_or_none()
                if not video:
                    return None
                video.status = status
                video.error_message = error
            await session.refresh(video)
            return video

    async def update_video_metadata(
        self,
        video_id: str,
        title: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        summary: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Video]:
        """Update metadata fields of a video."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = select(Video).where(Video.video_id == video_id)
                result = await session.execute(stmt)
                video = result.scalar_one_or_none()
                if not video:
                    return None
                if title is not None:
                    video.title = title
                if duration_seconds is not None:
                    video.duration_seconds = duration_seconds
                if summary is not None:
                    video.summary = summary
                if status is not None:
                    video.status = status
            await session.refresh(video)
            return video

    async def save_transcript_segments(
        self, video_pk: uuid.UUID, segments: Sequence[ProviderSegment]
    ) -> None:
        """Bulk save raw transcript segments for a video."""
        async with self.session_factory() as session:
            async with session.begin():
                db_segments = [
                    TranscriptSegment(
                        video_id=video_pk,
                        text=seg.text,
                        start_time=seg.start,
                        end_time=seg.end,
                        segment_index=idx,
                    )
                    for idx, seg in enumerate(segments)
                ]
                session.add_all(db_segments)

    async def save_chunks(
        self,
        video_pk: uuid.UUID,
        chunks: Sequence[CoreChunk],
        embeddings: Sequence[List[float]],
    ) -> None:
        """Bulk save chunk records along with their vector embeddings."""
        async with self.session_factory() as session:
            async with session.begin():
                db_chunks = [
                    Chunk(
                        video_id=video_pk,
                        text=chunk.text,
                        start_time=chunk.start_time,
                        end_time=chunk.end_time,
                        token_count=chunk.token_count,
                        embedding=emb,
                    )
                    for chunk, emb in zip(chunks, embeddings)
                ]
                session.add_all(db_chunks)

    async def get_chunks_by_time_range(
        self, video_id: str, start: float, end: float
    ) -> List[Chunk]:
        """Get chunks that overlap with the time range [start, end]."""
        async with self.session_factory() as session:
            stmt = (
                select(Chunk)
                .join(Video, Chunk.video_id == Video.id)
                .where(
                    Video.video_id == video_id,
                    Chunk.start_time <= end,
                    Chunk.end_time >= start,
                )
                .order_by(Chunk.start_time.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def search_similar_chunks(
        self, video_id: str, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[Chunk, float]]:
        """Perform pgvector cosine similarity search filtered by video_id.

        Returns list of (Chunk, similarity) tuples where similarity is
        1.0 - cosine_distance.
        """
        async with self.session_factory() as session:
            # Chunk.embedding.cosine_distance calculates cosine distance (0 to 2)
            distance_col = Chunk.embedding.cosine_distance(query_embedding).label(
                "distance"
            )
            stmt = (
                select(Chunk, distance_col)
                .join(Video, Chunk.video_id == Video.id)
                .where(Video.video_id == video_id)
                .order_by(distance_col.asc())
                .limit(top_k)
            )
            result = await session.execute(stmt)
            rows = result.all()
            # Convert cosine distance to cosine similarity (1.0 - distance)
            return [(row[0], max(0.0, 1.0 - float(row[1]))) for row in rows]

    async def get_transcript_segments(
        self,
        video_id: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> List[TranscriptSegment]:
        """Fetch transcript segments for a video, optionally filtered by time."""
        async with self.session_factory() as session:
            stmt = (
                select(TranscriptSegment)
                .join(Video, TranscriptSegment.video_id == Video.id)
                .where(Video.video_id == video_id)
            )
            if start is not None and end is not None:
                stmt = stmt.where(
                    TranscriptSegment.start_time <= end,
                    TranscriptSegment.end_time >= start,
                )
            stmt = stmt.order_by(TranscriptSegment.segment_index.asc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_chat_message(
        self,
        video_pk: uuid.UUID,
        session_id: str,
        role: str,
        content: str,
        current_time: Optional[float] = None,
        intent: Optional[str] = None,
        chunks_used: Optional[Any] = None,
    ) -> ChatMessage:
        """Insert a chat message record."""
        async with self.session_factory() as session:
            async with session.begin():
                msg = ChatMessage(
                    video_id=video_pk,
                    session_id=session_id,
                    role=role,
                    content=content,
                    current_time=current_time,
                    intent=intent,
                    chunks_used=chunks_used,
                )
                session.add(msg)
            await session.refresh(msg)
            return msg

    async def get_chat_history(
        self, video_id: str, session_id: str, limit: int = 20
    ) -> List[ChatMessage]:
        """Fetch recent chat messages for a video and session ordered by created_at ascending."""
        async with self.session_factory() as session:
            stmt = (
                select(ChatMessage)
                .join(Video, ChatMessage.video_id == Video.id)
                .where(
                    Video.video_id == video_id,
                    ChatMessage.session_id == session_id,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            messages = list(result.scalars().all())
            messages.reverse()  # chronological order
            return messages

