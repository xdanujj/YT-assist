from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.database import Base


class MessageRole(enum.Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"


class ChatSession(Base):
    """
    Represents a conversation associated with a video.
    Each session has many messages.
    """
    __tablename__ = "chat_sessions"

    session_id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    video = relationship("Video", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    def __repr__(self):
        return f"<ChatSession(session_id={self.session_id}, video_id={self.video_id})>"


class ChatMessage(Base):
    """
    Stores user questions and AI answers, including the video timestamp.
    """
    __tablename__ = "chat_messages"

    message_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    video_timestamp = Column(Float, nullable=True)  # Current video position in seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(message_id={self.message_id}, role={self.role.value}, session_id={self.session_id})>"
