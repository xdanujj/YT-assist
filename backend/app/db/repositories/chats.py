from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession, MessageRole


def get_session(db: Session, *, session_id: int, video_id: int) -> ChatSession | None:
    return db.scalar(
        select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.video_id == video_id,
        )
    )


def get_or_create_session(
    db: Session, *, video_id: int, session_id: int | None = None
) -> ChatSession:
    session = get_session(db, session_id=session_id, video_id=video_id) if session_id else None
    if session is None:
        session = ChatSession(video_id=video_id)
        db.add(session)
        db.flush()
    return session


def add_message(
    db: Session,
    *,
    session_id: int,
    role: MessageRole,
    content: str,
    video_timestamp: float | None,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        video_timestamp=video_timestamp,
    )
    db.add(message)
    db.flush()
    return message
