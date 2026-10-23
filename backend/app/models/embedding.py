from sqlalchemy import Column, Integer, String, LargeBinary, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ChunkEmbedding(Base):
    """
    Supports semantic search for questions about earlier concepts.
    chunk_id is both PK and FK to transcript_chunks.
    """
    __tablename__ = "chunk_embeddings"

    chunk_id = Column(
        Integer,
        ForeignKey("transcript_chunks.chunk_id", ondelete="CASCADE"),
        primary_key=True
    )
    embedding = Column(LargeBinary, nullable=False)  # Stored as binary blob
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chunk = relationship("TranscriptChunk", back_populates="embedding")

    def __repr__(self):
        return f"<ChunkEmbedding(chunk_id={self.chunk_id}, model='{self.model_name}')>"
