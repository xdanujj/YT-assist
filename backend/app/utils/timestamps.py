from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    """Format a non-negative duration as H:MM:SS or M:SS."""
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
