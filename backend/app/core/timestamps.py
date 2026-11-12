"""Timestamp parsing and formatting utilities — PURE functions, no I/O."""

from __future__ import annotations

import re

# Matches [H:MM:SS], [MM:SS], or bare H:MM:SS / MM:SS
_TS_BRACKET_RE = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")
_TS_BARE_RE = re.compile(r"(\d{1,2}:\d{2}(?::\d{2})?)")


def seconds_to_mmss(seconds: float) -> str:
    """Convert *seconds* to ``[MM:SS]`` or ``[H:MM:SS]`` format.

    Negative values are clamped to 0.
    """
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"[{hours}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes:02d}:{secs:02d}]"


def mmss_to_seconds(mmss: str) -> float:
    """Parse ``[MM:SS]``, ``[H:MM:SS]``, or bare ``MM:SS`` / ``H:MM:SS`` to seconds.

    Raises :class:`ValueError` if the string cannot be parsed.
    """
    cleaned = mmss.strip().strip("[]")
    parts = cleaned.split(":")
    if len(parts) == 2:
        minutes, secs = parts
        return int(minutes) * 60 + int(secs)
    if len(parts) == 3:
        hours, minutes, secs = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(secs)
    raise ValueError(f"Cannot parse timestamp: {mmss!r}")


def format_timestamp_link(seconds: float) -> str:
    """Return a ``[MM:SS]`` (or ``[H:MM:SS]``) formatted string for LLM responses."""
    return seconds_to_mmss(seconds)


def validate_timestamps_in_text(text: str, max_duration: float) -> str:
    """Find all ``[MM:SS]`` / ``[H:MM:SS]`` timestamps in *text* and remove any
    whose value exceeds *max_duration* (seconds).  Returns cleaned text.
    """

    def _replace(match: re.Match) -> str:
        try:
            ts_seconds = mmss_to_seconds(match.group(1))
        except ValueError:
            return match.group(0)
        if ts_seconds > max_duration:
            return ""
        return match.group(0)

    return _TS_BRACKET_RE.sub(_replace, text)


def get_time_window(
    current_time: float,
    window_seconds: float = 120.0,
) -> tuple[float, float]:
    """Return ``(start, end)`` centred on *current_time*, clamped so start ≥ 0."""
    half = window_seconds / 2.0
    start = max(0.0, current_time - half)
    end = current_time + half
    return (start, end)
