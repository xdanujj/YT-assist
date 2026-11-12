"""Retrieval ranking and merging — PURE functions, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass
class ScoredChunk:
    """A chunk with a similarity score and source tag."""
    text: str
    start_time: float
    end_time: float
    similarity: float
    source: str  # "local" or "global"


# ---------------------------------------------------------------------------
# Time-overlap helpers
# ---------------------------------------------------------------------------

def compute_time_overlap(
    a_start: float,
    a_end: float,
    b_start: float,
    b_end: float,
) -> float:
    """Return the overlap ratio (0.0–1.0) between two time ranges.

    The ratio is ``intersection / min(len_a, len_b)`` so that a short chunk
    fully contained in a longer one gives 1.0.  Returns 0.0 when either
    range has zero length.
    """
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    intersection = max(0.0, overlap_end - overlap_start)

    len_a = a_end - a_start
    len_b = b_end - b_start
    shorter = min(len_a, len_b)
    if shorter <= 0:
        return 0.0
    return intersection / shorter


# ---------------------------------------------------------------------------
# Merge & de-duplicate
# ---------------------------------------------------------------------------

_LOCAL_BOOST = 0.05  # small relevance boost for local (time-window) chunks
_OVERLAP_THRESHOLD = 0.80  # consider chunks duplicate above this overlap


def merge_and_dedup(
    local_chunks: list[ScoredChunk],
    global_chunks: list[ScoredChunk],
    max_chunks: int = 6,
) -> list[ScoredChunk]:
    """Merge local (time-window) and global (semantic) chunks.

    * Local chunks receive a small similarity boost (+0.05).
    * Duplicates (time-range overlap > 80%) are removed, keeping the
      higher-scored version.
    * The merged list is sorted by effective similarity descending and
      truncated to *max_chunks*.
    """
    # Apply boost to local chunks.
    boosted: list[ScoredChunk] = []
    for c in local_chunks:
        boosted.append(replace(c, similarity=c.similarity + _LOCAL_BOOST))
    boosted.extend(global_chunks)

    # Sort descending by similarity so we keep higher-scored duplicates.
    boosted.sort(key=lambda c: c.similarity, reverse=True)

    deduped: list[ScoredChunk] = []
    for candidate in boosted:
        is_dup = False
        for kept in deduped:
            if compute_time_overlap(
                candidate.start_time, candidate.end_time,
                kept.start_time, kept.end_time,
            ) > _OVERLAP_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            deduped.append(candidate)

    return deduped[:max_chunks]


# ---------------------------------------------------------------------------
# Re-ranking helpers
# ---------------------------------------------------------------------------

def rerank_for_explain(
    chunks: list[ScoredChunk],
    current_time: float,
) -> list[ScoredChunk]:
    """Re-rank chunks for the *explain_better* intent.

    * Chunks immediately before current_time (last 1-2 minutes) get the strongest boost.
    * Chunks earlier in the video get a smaller prerequisite boost.
    * Chunks after current_time are left unboosted.

    Returns a new list sorted by boosted similarity descending.
    """
    result: list[ScoredChunk] = []
    for c in chunks:
        boost = 0.0
        if c.start_time <= current_time:
            time_diff = current_time - c.start_time
            if time_diff <= 60.0:
                # Immediately before: peak recent context
                boost = 0.15
            elif time_diff <= 120.0:
                # 1-2 minutes before: strong recent context
                boost = 0.10
            else:
                # Earlier material: prerequisite boost
                boost = 0.03
        result.append(replace(c, similarity=c.similarity + boost))

    result.sort(key=lambda c: c.similarity, reverse=True)
    return result


def check_relevance_threshold(
    chunks: list[ScoredChunk],
    min_similarity: float = 0.35,
) -> bool:
    """Return ``True`` if at least one chunk meets *min_similarity*."""
    return any(c.similarity >= min_similarity for c in chunks)
