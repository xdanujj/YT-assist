from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"
    __table_args__ = (Index("ix_transcript_chunks_video_start", "video_id", "start_time"),)

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    video = relationship("Video", back_populates="transcript_chunks")
    embedding = relationship(
        "ChunkEmbedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TranscriptChunk(chunk_id={self.chunk_id}, video_id={self.video_id})>"
