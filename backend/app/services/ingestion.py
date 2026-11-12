"""Video ingestion pipeline service."""

from __future__ import annotations

import logging
from typing import Optional

from app.config import get_settings
from app.core.chunking import TranscriptSegment as CoreSegment, chunk_transcript
from app.db.repo import VideoRepository
from app.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    TranscriptNotAvailable,
    TranscriptProvider,
)
from app.schemas import VideoStatus, VideoStatusResponse

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the YouTube video ingestion pipeline."""

    def __init__(
        self,
        repo: VideoRepository,
        transcript_provider: TranscriptProvider,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
    ) -> None:
        self.repo = repo
        self.transcript_provider = transcript_provider
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider

    async def get_video_status(self, video_id: str) -> VideoStatusResponse:
        """Fetch current indexing status of a video."""
        video = await self.repo.get_video(video_id)
        if not video:
            return VideoStatusResponse(
                video_id=video_id,
                status=VideoStatus.pending,
            )

        try:
            status_enum = VideoStatus(video.status)
        except ValueError:
            status_enum = VideoStatus.pending

        return VideoStatusResponse(
            video_id=video_id,
            status=status_enum,
            title=video.title,
            duration=video.duration_seconds,
            summary=video.summary,
            error=video.error_message,
        )

    async def ingest_video(self, video_id: str) -> VideoStatusResponse:
        """Execute the ingestion pipeline for a video.

        Steps:
        1. Check if video is already ready -> skip.
        2. Set status to processing.
        3. Fetch metadata and transcript.
        4. Store raw transcript segments.
        5. Chunk transcript.
        6. Compute embeddings for chunks and store them.
        7. Generate a video summary.
        8. Set status to ready.
        """
        # Step 1: Check if already ready or processing
        existing = await self.repo.get_video(video_id)
        if existing and existing.status == "ready":
            logger.info("Video %s is already indexed and ready", video_id)
            return VideoStatusResponse(
                video_id=video_id,
                status=VideoStatus.ready,
                title=existing.title,
                duration=existing.duration_seconds,
                summary=existing.summary,
            )

        # Step 2: Register or update to processing
        video = await self.repo.get_or_create_video(video_id)
        await self.repo.update_video_status(video_id, "processing")

        try:
            # Step 3: Fetch metadata & transcript
            metadata = await self.transcript_provider.fetch_video_metadata(video_id)
            title = metadata.get("title")
            duration = metadata.get("duration_seconds")

            raw_segments = await self.transcript_provider.fetch_transcript(video_id)
            if not raw_segments:
                raise TranscriptNotAvailable(video_id, reason="No transcript segments returned")

            if duration is None and raw_segments:
                duration = raw_segments[-1].end

            # Step 4: Store raw transcript segments
            await self.repo.save_transcript_segments(video.id, raw_segments)

            # Step 5: Chunk transcript
            settings = get_settings()
            core_segments = [
                CoreSegment(text=s.text, start=s.start, end=s.end)
                for s in raw_segments
            ]
            chunks = chunk_transcript(
                core_segments,
                target_tokens=settings.chunk_target_tokens,
                overlap_ratio=settings.chunk_overlap_ratio,
            )

            if not chunks:
                raise ValueError("Chunking produced 0 chunks from transcript")

            # Step 6: Embed chunks and save
            chunk_texts = [c.text for c in chunks]
            embeddings = await self.embedding_provider.embed(chunk_texts)
            await self.repo.save_chunks(video.id, chunks, embeddings)

            # Step 7: Generate video summary
            summary = None
            try:
                # Use first ~8 chunks as representation for video summary
                sample_text = "\n\n".join(chunk_texts[:8])
                summary_prompt = (
                    f"Based on the following transcript excerpts from the video '{title or video_id}', "
                    "provide a concise 2-3 paragraph summary of the key concepts and topics covered:\n\n"
                    f"{sample_text}"
                )
                summary = await self.llm_provider.generate(
                    prompt=summary_prompt,
                    system="You are an expert educational AI tutor. Summarize clearly and objectively.",
                )
            except Exception as exc:
                logger.warning("Could not generate summary for %s: %s", video_id, exc)

            # Step 8: Update video record to ready
            await self.repo.update_video_metadata(
                video_id=video_id,
                title=title,
                duration_seconds=duration,
                summary=summary,
                status="ready",
            )

            logger.info("Successfully ingested video %s (%d chunks)", video_id, len(chunks))
            return VideoStatusResponse(
                video_id=video_id,
                status=VideoStatus.ready,
                title=title,
                duration=duration,
                summary=summary,
            )

        except Exception as exc:
            err_msg = str(exc)
            logger.error("Ingestion failed for video %s: %s", video_id, err_msg, exc_info=True)
            await self.repo.update_video_status(video_id, "failed", error=err_msg)
            return VideoStatusResponse(
                video_id=video_id,
                status=VideoStatus.failed,
                error=err_msg,
            )

