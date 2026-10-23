from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.database import Base


class TranscriptStatus(enum.Enum):
    """Status of transcript processing for a video."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    """
    Stores each YouTube video processed by the extension.
    One video has many transcript chunks.
    """
    __tablename__ = "videos"

    video_id = Column(Integer, primary_key=True, index=True)
    youtube_id = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=True)
    url = Column(String(500), nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    transcript_status = Column(
        Enum(TranscriptStatus),
        default=TranscriptStatus.PENDING,
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    transcript_chunks = relationship(
        "TranscriptChunk",
        back_populates="video",
        cascade="all, delete-orphan"
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="video",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Video(video_id={self.video_id}, youtube_id='{self.youtube_id}', title='{self.title}')>"
