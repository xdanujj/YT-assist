from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptChunkCreate(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    start_time: float = Field(ge=0)
    end_time: float = Field(ge=0)


class TranscriptResponse(BaseModel):
    video_id: str
    status: str
    chunks: list[TranscriptChunkCreate]
