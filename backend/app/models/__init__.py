"""
SQLAlchemy models for YouTube Tutor database.

Models:
    - Video: YouTube videos processed by the extension
    - TranscriptChunk: Timestamped transcript text
    - ChunkEmbedding: Semantic search embeddings
    - ChatSession: Conversations associated with videos
    - ChatMessage: User questions and AI answers
"""

from app.models.video import Video, TranscriptStatus
from app.models.transcript import TranscriptChunk
from app.models.embedding import ChunkEmbedding
from app.models.chat import ChatSession, ChatMessage, MessageRole

__all__ = [
    "Video",
    "TranscriptStatus",
    "TranscriptChunk",
    "ChunkEmbedding",
    "ChatSession",
    "ChatMessage",
    "MessageRole",
]
