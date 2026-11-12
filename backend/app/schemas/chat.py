from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    current_time: float = Field(default=0, ge=0)
    session_id: int | None = Field(default=None, gt=0)


class Citation(BaseModel):
    chunk_id: int
    text: str
    start_time: float
    end_time: float
    timestamp: str


class ChatResponse(BaseModel):
    answer: str
    session_id: int
    citations: list[Citation]
