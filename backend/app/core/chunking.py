"""Transcript chunking logic — PURE functions, no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    """A single caption / subtitle segment from the transcript."""
    text: str
    start: float
    end: float


@dataclass
class Chunk:
    """A merged chunk of transcript segments with time boundaries."""
    text: str
    start_time: float
    end_time: float
    token_count: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate: split on whitespace and count.

    Good enough for chunking purposes — actual tokeniser lives elsewhere.
    """
    return len(text.split())


# Sentence-ending punctuation used to find good break points.
_SENTENCE_ENDS = {".", "?", "!"}


def _find_sentence_break(segments: list[TranscriptSegment], window: int = 3) -> int | None:
    """Look backwards through the last *window* segments for a sentence boundary.

    Returns the 1-based index (suitable as a slice end) of the segment whose
    text ends with sentence-ending punctuation, or ``None`` if no break is
    found.
    """
    start = max(0, len(segments) - window)
    for i in range(len(segments) - 1, start - 1, -1):
        stripped = segments[i].text.rstrip()
        if stripped and stripped[-1] in _SENTENCE_ENDS:
            return i + 1  # slice-end: include this segment
    return None


def chunk_transcript(
    segments: list[TranscriptSegment],
    target_tokens: int = 400,
    overlap_ratio: float = 0.12,
) -> list[Chunk]:
    """Chunk transcript segments by token budget with overlap.

    Algorithm
    ---------
    1. Accumulate adjacent segments into a growing chunk until *target_tokens*
       is reached.
    2. When a chunk reaches *target_tokens*, try to break at a sentence
       boundary (period / question-mark in the last few segments).  If found,
       finalise there; otherwise finalise at the current segment.
    3. Start the next chunk with the last *N* segments of the previous one so
       that roughly ``target_tokens * overlap_ratio`` tokens overlap.
    4. Each :class:`Chunk` records ``start_time`` / ``end_time`` from its
       constituent segments.
    """
    if not segments:
        return []

    overlap_tokens = int(target_tokens * overlap_ratio)
    chunks: list[Chunk] = []

    # ``pending`` holds segments that belong to the chunk we are building.
    pending: list[TranscriptSegment] = []
    pending_tokens = 0

    def _finalise(segs: list[TranscriptSegment]) -> Chunk:
        text = " ".join(s.text for s in segs)
        return Chunk(
            text=text,
            start_time=segs[0].start,
            end_time=segs[-1].end,
            token_count=estimate_tokens(text),
        )

    def _compute_overlap_start(segs: list[TranscriptSegment]) -> int:
        """Return the index into *segs* where overlap should begin."""
        cumulative = 0
        for idx in range(len(segs) - 1, -1, -1):
            cumulative += estimate_tokens(segs[idx].text)
            if cumulative >= overlap_tokens:
                return idx
        return 0

    for seg in segments:
        seg_tokens = estimate_tokens(seg.text)
        pending.append(seg)
        pending_tokens += seg_tokens

        if pending_tokens >= target_tokens:
            # Try to break at a sentence boundary in the last few segments.
            break_idx = _find_sentence_break(pending)
            if break_idx is not None and break_idx >= 1:
                chunk_segs = pending[:break_idx]
                leftover = pending[break_idx:]
            else:
                chunk_segs = list(pending)
                leftover = []

            chunks.append(_finalise(chunk_segs))

            # Build overlap from the finalised chunk's tail.
            overlap_start = _compute_overlap_start(chunk_segs)
            overlap_segs = chunk_segs[overlap_start:]

            # New pending = overlap + any leftover segments that didn't make it
            pending = overlap_segs + leftover
            pending_tokens = sum(estimate_tokens(s.text) for s in pending)

    # Flush remaining segments.
    if pending:
        chunks.append(_finalise(pending))

    return chunks
