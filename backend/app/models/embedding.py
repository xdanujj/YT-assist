"""Vector storage model for transcript chunks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # Keep imports usable before optional dependency installation.
    Vector = None  # type: ignore[assignment,misc]


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("transcript_chunks.chunk_id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(get_settings().embedding_dimension) if Vector else String,
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunk = relationship("TranscriptChunk", back_populates="embedding")

    def __repr__(self) -> str:
        return f"<ChunkEmbedding(chunk_id={self.chunk_id}, model='{self.model_name}')>"
