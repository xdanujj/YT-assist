"""Pydantic request / response models for the YouTube Tutor API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ── Enums ───────────────────────────────────────────────────────────────────


class VideoStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Intent(str, Enum):
    lookup = "lookup"
    explain_better = "explain_better"
    summarize = "summarize"
    out_of_scope = "out_of_scope"


class ExplainMode(str, Enum):
    simpler = "simpler"
    analogy = "analogy"
    example = "example"
    prerequisite = "prerequisite"


# ── Request models ──────────────────────────────────────────────────────────


class RegisterVideoRequest(BaseModel):
    video_id: str


class AskRequest(BaseModel):
    video_id: str
    question: str
    session_id: str
    current_time: float  # seconds into the video
    mode: Optional[ExplainMode] = None


# ── Response models ─────────────────────────────────────────────────────────


class VideoStatusResponse(BaseModel):
    video_id: str
    status: VideoStatus
    title: Optional[str] = None
    duration: Optional[float] = None
    summary: Optional[str] = None
    error: Optional[str] = None


class TranscriptSegment(BaseModel):
    text: str
    start: float
    end: float


class ChunkInfo(BaseModel):
    text: str
    start_time: float
    end_time: float
    similarity: float


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime
    chunks_used: Optional[List[ChunkInfo]] = None


class HistoryResponse(BaseModel):
    messages: List[ChatMessage]


class AskResponseChunk(BaseModel):
    type: str  # "token" | "done" | "error"
    content: Optional[str] = None
    chunks_used: Optional[List[ChunkInfo]] = None
