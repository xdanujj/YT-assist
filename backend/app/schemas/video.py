from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class VideoRegisterRequest(BaseModel):
    video_id: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    duration_seconds: float | None = Field(default=None, ge=0)
    force_reindex: bool = False


class VideoRegisterResponse(BaseModel):
    video_id: str
    status: str
    indexing_started: bool
    chunk_count: int = 0


class VideoStatusResponse(BaseModel):
    video_id: str
    status: str
    chunk_count: int = 0
    error: str | None = None


class TranscriptChunkResponse(BaseModel):
    chunk_id: int
    text: str
    start_time: float
    end_time: float
    timestamp: str


class VideoDetailResponse(BaseModel):
    video_id: str
    title: str | None
    status: str
    chunks: list[TranscriptChunkResponse] = []
