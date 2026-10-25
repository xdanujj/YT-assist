
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from dotenv import load_dotenv
from app.schemas.test_data import (
    VideoCaptureRequest,
    VideoCaptureResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test", tags=["test-data"])

TEST_DATA_DIRECTORY = Path(__file__).resolve().parents[3] / "test_data"
SERPAPI_TRANSCRIPT_URL = "https://serpapi.com/search.json"
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


'''TESTING SERP API KEY: 1'''
    
def fetch_transcript(
    video_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch YouTube captions through SerpApi's YouTube Video Transcript API.

    Returns:
        A status string and a list of transcript chunks.
    """
    api_key = (
        os.environ.get("SERP_API_KEY")
        or os.environ.get("SERPAPI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        logger.error("SERP_API_KEY is not configured")
        return "unavailable: MissingSerpApiKey", []

    params = urlencode(
        {
            "engine": "youtube_video_transcript",
            "v": video_id,
            "api_key": api_key,
            "output": "json",
        }
    )

    try:
        with urlopen(f"{SERPAPI_TRANSCRIPT_URL}?{params}", timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

        if result.get("search_metadata", {}).get("status") != "Success":
            detail = result.get("error") or result.get("search_metadata", {}).get("status") or "UnknownError"
            logger.warning("SerpApi transcript request failed for %s: %s", video_id, detail)
            return f"unavailable: {detail}", []

        chunks = [
            {
                "text": item.get("snippet", ""),
                "start_time": (item.get("start_ms", 0) or 0) / 1000,
                "duration": max(
                    0,
                    ((item.get("end_ms", 0) or 0) - (item.get("start_ms", 0) or 0)) / 1000,
                ),
                "start_time_text": item.get("start_time_text"),
            }
            for item in result.get("transcript", [])
            if item.get("snippet")
        ]

        if not chunks:
            logger.warning(
                "Transcript returned no chunks for video %s",
                video_id,
            )
            return "unavailable: EmptyTranscript", []

        logger.info(
            "Transcript fetched successfully for video %s (%d chunks)",
            video_id,
            len(chunks),
        )

        return "available", chunks

    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        logger.exception(
            "SerpApi transcript request failed for video %s",
            video_id,
        )
        return f"unavailable: {type(error).__name__}", []


def load_existing_record(file_path: Path) -> dict[str, Any]:
    """Load an existing JSON record, if it is valid."""
    if not file_path.exists():
        return {}

    try:
        with file_path.open("r", encoding="utf-8") as json_file:
            record = json.load(json_file)

        if isinstance(record, dict):
            return record

        logger.warning(
            "Existing record is not a JSON object: %s",
            file_path,
        )
        return {}

    except (OSError, json.JSONDecodeError) as error:
        logger.warning(
            "Could not load existing record %s: %s",
            file_path,
            error,
        )
        return {}


def write_record(
    file_path: Path,
    record: dict[str, Any],
) -> None:
    """Atomically write a JSON record."""
    temporary_path = file_path.with_suffix(".tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as json_file:
            json.dump(
                record,
                json_file,
                ensure_ascii=False,
                indent=2,
            )
            json_file.write("\n")

        os.replace(temporary_path, file_path)

    finally:
        # Remove a leftover temporary file if writing or replacement fails.
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "Could not remove temporary file %s",
                temporary_path,
            )


@router.post(
    "/video-data",
    response_model=VideoCaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_video_capture(
    payload: VideoCaptureRequest,
) -> VideoCaptureResponse:
    """
    Save the latest video state and append the submitted chat event.

    Retries transcript retrieval whenever the previously stored transcript
    status is not available.
    """
    try:
        TEST_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

        # Prevent a video ID from being interpreted as a path.
        video_id = payload.video_id.strip()

        if (
            not video_id
            or "/" in video_id
            or "\\" in video_id
            or video_id in {".", ".."}
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid video ID.",
            )

        file_path = TEST_DATA_DIRECTORY / f"{video_id}.json"
        record = load_existing_record(file_path)

        transcript_status = record.get("transcript_status")
        transcript_chunks = record.get("transcript_chunks", [])

        # Reuse a successful transcript. Retry any failed or missing result.
        if (
            transcript_status != "available"
            or not isinstance(transcript_chunks, list)
            or not transcript_chunks
        ):
            transcript_status, transcript_chunks = fetch_transcript(
                video_id
            )

        captured_at = datetime.now(UTC).isoformat()

        chat_event = {
            "message": payload.message,
            "current_timestep": payload.current_timestep,
            "is_playing": payload.is_playing,
            "captured_at": captured_at,
        }

        # Preserve the existing chat history and update the latest video data.
        record.update(
            {
                "video_id": video_id,
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

        chat_events = record.get("chat_events")

        if not isinstance(chat_events, list):
            chat_events = []
            record["chat_events"] = chat_events

        chat_events.append(chat_event)

        write_record(file_path, record)

        logger.info(
            "Saved video capture: %s; transcript=%s; chunks=%d",
            video_id,
            transcript_status,
            len(transcript_chunks),
        )

        return VideoCaptureResponse(
            file_name=file_path.name,
            transcript_status=transcript_status,
            transcript_chunk_count=len(transcript_chunks),
        )

    except HTTPException:
        raise

    except OSError as error:
        logger.exception("Could not write video capture data")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not write the test data file.",
        ) from error
