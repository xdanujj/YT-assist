import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from youtube_transcript_api import YouTubeTranscriptApi

from app.schemas.test_data import VideoCaptureRequest, VideoCaptureResponse

router = APIRouter(prefix="/api/test", tags=["test-data"])
TEST_DATA_DIRECTORY = Path(__file__).resolve().parents[3] / "test_data"


def fetch_transcript(video_id: str) -> tuple[str, list[dict[str, float | str]]]:
    """Fetch public captions for a video without exposing transcript failures as API crashes."""
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id)
        return "available", [
            {
                "text": snippet.text,
                "start_time": snippet.start,
                "duration": snippet.duration,
            }
            for snippet in transcript
        ]
    except Exception as error:
        return f"unavailable: {error.__class__.__name__}", []


def load_existing_record(file_path: Path) -> dict:
    if not file_path.exists():
        return {}

    try:
        with file_path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except (OSError, json.JSONDecodeError):
        return {}


def write_record(file_path: Path, record: dict) -> None:
    """Atomically replace the output file so partial JSON is never left behind."""
    temporary_path = file_path.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as json_file:
        json.dump(record, json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")
    os.replace(temporary_path, file_path)


@router.post("/video-data", response_model=VideoCaptureResponse, status_code=status.HTTP_201_CREATED)
def save_video_capture(payload: VideoCaptureRequest) -> VideoCaptureResponse:
    """Fetch a transcript and store the latest video state plus all submitted chat events."""
    TEST_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = TEST_DATA_DIRECTORY / f"{payload.video_id}.json"
    record = load_existing_record(file_path)

    transcript_status = record.get("transcript_status")
    transcript_chunks = record.get("transcript_chunks", [])
    if not transcript_status:
        transcript_status, transcript_chunks = fetch_transcript(payload.video_id)

    captured_at = datetime.now(UTC).isoformat()
    chat_event = {
        "message": payload.message,
        "current_timestep": payload.current_timestep,
        "is_playing": payload.is_playing,
        "captured_at": captured_at,
    }
    record.update(
        {
            "video_id": payload.video_id,
            "title": payload.title,
            "url": str(payload.url),
            "video_duration": payload.video_duration,
            "current_timestep": payload.current_timestep,
            "is_playing": payload.is_playing,
            "updated_at": captured_at,
            "transcript_status": transcript_status,
            "transcript_chunks": transcript_chunks,
        }
    )
    record.setdefault("chat_events", []).append(chat_event)

    try:
        write_record(file_path, record)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Could not write the test data file.") from error

    return VideoCaptureResponse(
        file_name=file_path.name,
        transcript_status=transcript_status,
        transcript_chunk_count=len(transcript_chunks),
    )
