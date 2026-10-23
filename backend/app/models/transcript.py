from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TranscriptChunk(Base):
    """
    Stores timestamped transcript text for retrieving the current topic.
    Each chunk can have an embedding.
    """
    __tablename__ = "transcript_chunks"

    chunk_id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    start_time = Column(Float, nullable=False)  # seconds
    end_time = Column(Float, nullable=False)    # seconds
    text = Column(Text, nullable=False)
    topic = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video", back_populates="transcript_chunks")
    embedding = relationship(
        "ChunkEmbedding",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<TranscriptChunk(chunk_id={self.chunk_id}, video_id={self.video_id}, start={self.start_time}s)>"
