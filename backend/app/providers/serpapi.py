"""SerpApi-based transcript provider for YouTube videos."""

import logging

import httpx

from app.config import get_settings
from app.providers.base import (
    TranscriptNotAvailable,
    TranscriptProvider,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)


def _parse_duration_to_seconds(duration_str: str) -> float | None:
    """Parse a duration string like '10:30' or '1:02:15' into total seconds.

    Args:
        duration_str: Duration in HH:MM:SS or MM:SS format.

    Returns:
        Total seconds as a float, or None if parsing fails.
    """
    if not duration_str:
        return None
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 1:
            return float(parts[0])
    except (ValueError, TypeError):
        return None
    return None


class SerpApiTranscript(TranscriptProvider):
    """Transcript provider that uses SerpApi's YouTube Transcript API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.serpapi_key

    async def fetch_transcript(self, video_id: str) -> list[TranscriptSegment]:
        """Fetch transcript segments from SerpApi.

        Makes a GET request to the SerpApi YouTube Transcript engine and
        converts the response into a list of TranscriptSegment objects.
        """
        params = {
            "engine": "youtube_transcript",
            "video_id": video_id,
            "api_key": self._api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("https://serpapi.com/search", params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            raise TranscriptNotAvailable(video_id, reason="SerpApi request timed out")
        except httpx.HTTPStatusError as exc:
            raise TranscriptNotAvailable(
                video_id, reason=f"SerpApi returned HTTP {exc.response.status_code}"
            )
        except httpx.HTTPError as exc:
            raise TranscriptNotAvailable(video_id, reason=f"HTTP error: {exc}")

        # Check for API-level errors
        if "error" in data:
            raise TranscriptNotAvailable(video_id, reason=data["error"])

        raw_segments = data.get("transcript")
        if not raw_segments:
            raise TranscriptNotAvailable(
                video_id, reason="No transcript data in response"
            )

        segments: list[TranscriptSegment] = []
        for seg in raw_segments:
            try:
                start = float(seg["start"])
                duration = float(seg["duration"])
                segments.append(
                    TranscriptSegment(
                        text=seg.get("text", "").strip(),
                        start=start,
                        end=start + duration,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed transcript segment %s: %s", seg, exc)
                continue

        if not segments:
            raise TranscriptNotAvailable(
                video_id, reason="All transcript segments were malformed"
            )

        logger.info(
            "Fetched %d transcript segments for video %s", len(segments), video_id
        )
        return segments

    async def fetch_video_metadata(self, video_id: str) -> dict:
        """Fetch video metadata via SerpApi YouTube search.

        Searches for the video_id and attempts to match it in the results
        to extract the title and duration.
        """
        params = {
            "engine": "youtube",
            "search_query": video_id,
            "api_key": self._api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("https://serpapi.com/search", params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch metadata for video %s: %s", video_id, exc)
            return {"title": None, "duration_seconds": None}

        # Search video_results for a matching video_id
        video_results = data.get("video_results", [])
        for result in video_results:
            link = result.get("link", "")
            # Match video_id in the URL (e.g. watch?v=VIDEO_ID)
            if video_id in link:
                title = result.get("title")
                duration_str = result.get("length", result.get("duration", ""))
                duration_seconds = _parse_duration_to_seconds(duration_str)
                return {"title": title, "duration_seconds": duration_seconds}

        # No match found — return empty metadata
        logger.warning("No matching video found in SerpApi results for %s", video_id)
        return {"title": None, "duration_seconds": None}
