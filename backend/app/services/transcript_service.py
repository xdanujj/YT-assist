"""SerpApi transcript acquisition and normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config import get_settings

SERPAPI_TRANSCRIPT_URL = "https://serpapi.com/search.json"


class TranscriptError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptChunkData:
    text: str
    start_time: float
    end_time: float


def normalize_transcript(items: object) -> list[TranscriptChunkData]:
    if not isinstance(items, list):
        raise TranscriptError("Transcript payload is invalid")

    chunks: list[TranscriptChunkData] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("snippet") or "").strip()
        if not text:
            continue
        try:
            start_ms = float(item.get("start_ms", 0) or 0)
            end_ms = float(item.get("end_ms", start_ms) or start_ms)
        except (TypeError, ValueError) as exc:
            raise TranscriptError("Transcript contains an invalid timestamp") from exc
        if start_ms < 0 or end_ms < 0:
            raise TranscriptError("Transcript contains a negative timestamp")
        chunks.append(
            TranscriptChunkData(
                text=text,
                start_time=start_ms / 1000,
                end_time=max(start_ms, end_ms) / 1000,
            )
        )

    if not chunks:
        raise TranscriptError("No transcript is available for this video")
    return chunks


def fetch_transcript(video_id: str) -> list[TranscriptChunkData]:
    settings = get_settings()
    if not settings.serp_api_key:
        raise TranscriptError("Transcript provider is not configured")

    query = urlencode(
        {
            "engine": "youtube_video_transcript",
            "v": video_id,
            "api_key": settings.serp_api_key,
            "output": "json",
        }
    )
    try:
        with urlopen(f"{SERPAPI_TRANSCRIPT_URL}?{query}", timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise TranscriptError("Could not retrieve the video transcript") from exc

    if not isinstance(result, dict):
        raise TranscriptError("Transcript provider returned an invalid response")
    if result.get("search_metadata", {}).get("status") != "Success":
        raise TranscriptError("Transcript provider could not retrieve this video")
    return normalize_transcript(result.get("transcript"))
