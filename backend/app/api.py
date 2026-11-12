"""API router definition for video ingestion, status, chat queries, and history."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from starlette.responses import StreamingResponse

from app.schemas import (
    AskRequest,
    HistoryResponse,
    RegisterVideoRequest,
    VideoStatus,
    VideoStatusResponse,
)
from app.services.chat import ChatService
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def get_ingestion_service(request: Request) -> IngestionService:
    """Dependency provider for IngestionService from app state."""
    return request.app.state.ingestion_service


def get_chat_service(request: Request) -> ChatService:
    """Dependency provider for ChatService from app state."""
    return request.app.state.chat_service


# ── Health ──────────────────────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ── Videos ──────────────────────────────────────────────────────────────────


@router.post("/videos/register", response_model=VideoStatusResponse)
async def register_video(
    req: RegisterVideoRequest,
    background_tasks: BackgroundTasks,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """Register a YouTube video.

    If the video is already indexed or processing, returns current status.
    Otherwise schedules ingestion in the background and returns status: processing.
    """
    current_status = await ingestion_service.get_video_status(req.video_id)
    if current_status.status in (VideoStatus.ready, VideoStatus.processing):
        return current_status

    # Launch ingestion pipeline in background
    background_tasks.add_task(ingestion_service.ingest_video, req.video_id)

    return VideoStatusResponse(
        video_id=req.video_id,
        status=VideoStatus.processing,
    )


@router.get("/videos/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(
    video_id: str,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """Get indexing status of a YouTube video."""
    return await ingestion_service.get_video_status(video_id)


# ── Chat ────────────────────────────────────────────────────────────────────


@router.post("/chat/ask")
async def ask_question(
    req: AskRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Ask a question about the video with Server-Sent Events (SSE) streaming."""

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        async for chunk in chat_service.ask(
            video_id=req.video_id,
            question=req.question,
            session_id=req.session_id,
            current_time=req.current_time,
            mode=req.mode,
        ):
            yield f"data: {chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history/{video_id}/{session_id}", response_model=HistoryResponse)
async def get_chat_history(
    video_id: str,
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Fetch chat history for a video and session."""
    return await chat_service.get_history(video_id, session_id)

