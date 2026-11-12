from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transcript import TranscriptChunk
from app.models.video import TranscriptStatus, Video


def get_by_youtube_id(db: Session, youtube_id: str) -> Video | None:
    return db.scalar(select(Video).where(Video.youtube_id == youtube_id))


def upsert_video(
    db: Session,
    *,
    youtube_id: str,
    title: str,
    url: str,
    duration_seconds: float | None,
) -> Video:
    video = get_by_youtube_id(db, youtube_id)
    if video is None:
        video = Video(
            youtube_id=youtube_id,
            title=title,
            url=url,
            duration_seconds=duration_seconds,
            transcript_status=TranscriptStatus.PENDING,
        )
        db.add(video)
        db.flush()
        return video

    video.title = title
    video.url = url
    video.duration_seconds = duration_seconds
    db.flush()
    return video


def chunk_count(db: Session, video_id: int) -> int:
    return int(
        db.scalar(select(func.count(TranscriptChunk.chunk_id)).where(TranscriptChunk.video_id == video_id))
        or 0
    )
