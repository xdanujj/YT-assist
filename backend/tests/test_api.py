"""Integration and API route tests using FastAPI TestClient with mocked services."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    AskResponseChunk,
    ChatMessage,
    HistoryResponse,
    VideoStatus,
    VideoStatusResponse,
)


@pytest.fixture
def mock_services():
    """Mock application services and attach to app.state for testing."""
    mock_ingestion = MagicMock()
    mock_chat = MagicMock()

    mock_ingestion.get_video_status = AsyncMock(
        return_value=VideoStatusResponse(
            video_id="test1234",
            status=VideoStatus.ready,
            title="Introduction to Machine Learning",
            duration=300.0,
            summary="A quick intro to ML fundamentals.",
        )
    )
    mock_ingestion.ingest_video = AsyncMock(
        return_value=VideoStatusResponse(
            video_id="test1234",
            status=VideoStatus.ready,
            title="Introduction to Machine Learning",
            duration=300.0,
            summary="A quick intro to ML fundamentals.",
        )
    )

    mock_chat.get_history = AsyncMock(
        return_value=HistoryResponse(
            messages=[
                ChatMessage(
                    role="user",
                    content="What is supervised learning?",
                    timestamp=datetime.now(timezone.utc),
                ),
                ChatMessage(
                    role="assistant",
                    content="Supervised learning uses labeled data [01:30].",
                    timestamp=datetime.now(timezone.utc),
                ),
            ]
        )
    )

    async def mock_ask_gen(*args, **kwargs):
        yield AskResponseChunk(type="token", content="Supervised ")
        yield AskResponseChunk(type="token", content="learning is...")
        yield AskResponseChunk(type="done", content="Supervised learning is...")

    mock_chat.ask = mock_ask_gen

    app.state.ingestion_service = mock_ingestion
    app.state.chat_service = mock_chat

    return mock_ingestion, mock_chat


@pytest.fixture
def client(mock_services):
    """Test client with mocked dependencies."""
    return TestClient(app)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_video_status(client, mock_services):
    response = client.get("/api/videos/test1234/status")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "test1234"
    assert data["status"] == "ready"
    assert data["title"] == "Introduction to Machine Learning"


def test_register_video(client, mock_services):
    mock_ingestion, _ = mock_services
    # When already ready, returns ready
    response = client.post("/api/videos/register", json={"video_id": "test1234"})
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_get_chat_history(client, mock_services):
    response = client.get("/api/chat/history/test1234/sess99")
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"


def test_ask_question_sse(client, mock_services):
    payload = {
        "video_id": "test1234",
        "question": "Can you explain supervised learning?",
        "session_id": "sess99",
        "current_time": 45.0,
    }
    response = client.post("/api/chat/ask", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    lines = response.text.strip().split("\n\n")
    assert len(lines) >= 2
    assert "data:" in lines[0]

