"""Unit tests for pure core logic: timestamps, chunking, retrieval, and prompts."""

import pytest

from app.core.chunking import TranscriptSegment, chunk_transcript, estimate_tokens
from app.core.prompts import (
    build_rewrite_prompt,
    build_standalone_question,
    build_system_prompt,
    build_user_prompt,
    detect_intent,
)
from app.core.retrieval import (
    ScoredChunk,
    check_relevance_threshold,
    compute_time_overlap,
    merge_and_dedup,
    rerank_for_explain,
)
from app.core.timestamps import (
    format_timestamp_link,
    get_time_window,
    mmss_to_seconds,
    seconds_to_mmss,
    validate_timestamps_in_text,
)


# ── Timestamps Tests ────────────────────────────────────────────────────────


def test_seconds_to_mmss():
    assert seconds_to_mmss(0) == "[00:00]"
    assert seconds_to_mmss(65) == "[01:05]"
    assert seconds_to_mmss(3600) == "[1:00:00]"
    assert seconds_to_mmss(3665) == "[1:01:05]"
    assert seconds_to_mmss(-10) == "[00:00]"


def test_mmss_to_seconds():
    assert mmss_to_seconds("[00:00]") == 0
    assert mmss_to_seconds("01:05") == 65
    assert mmss_to_seconds("[1:00:00]") == 3600
    assert mmss_to_seconds("1:01:05") == 3665
    with pytest.raises(ValueError):
        mmss_to_seconds("invalid")


def test_format_timestamp_link():
    assert format_timestamp_link(125) == "[02:05]"


def test_validate_timestamps_in_text():
    text = "Check out [01:30] and also [10:00] for details."
    # max_duration 300 seconds (5 mins) -> [10:00] should be stripped
    cleaned = validate_timestamps_in_text(text, max_duration=300.0)
    assert "[01:30]" in cleaned
    assert "[10:00]" not in cleaned


def test_get_time_window():
    start, end = get_time_window(100.0, window_seconds=120.0)
    assert start == 40.0
    assert end == 160.0

    # Start shouldn't go below 0
    start, end = get_time_window(30.0, window_seconds=120.0)
    assert start == 0.0
    assert end == 90.0


# ── Chunking Tests ──────────────────────────────────────────────────────────


def test_estimate_tokens():
    text = "Hello world this is a test"
    assert estimate_tokens(text) == 6


def test_chunk_transcript():
    segments = [
        TranscriptSegment(text="Hello world.", start=0.0, end=2.0),
        TranscriptSegment(text="Welcome to the video course.", start=2.0, end=5.0),
        TranscriptSegment(text="In this video we talk about vectors.", start=5.0, end=9.0),
        TranscriptSegment(text="Vectors have magnitude and direction.", start=9.0, end=13.0),
        TranscriptSegment(text="That is all for now.", start=13.0, end=16.0),
    ]

    # Target small token limit to force chunking
    chunks = chunk_transcript(segments, target_tokens=8, overlap_ratio=0.2)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.start_time <= c.end_time
        assert len(c.text) > 0
        assert c.token_count > 0


# ── Retrieval Tests ─────────────────────────────────────────────────────────


def test_compute_time_overlap():
    # Identical ranges
    assert compute_time_overlap(0.0, 10.0, 0.0, 10.0) == 1.0
    # Partial overlap: [0, 10] and [5, 15] -> overlap [5, 10] = 5; shorter = 10 -> 0.5
    assert compute_time_overlap(0.0, 10.0, 5.0, 15.0) == 0.5
    # No overlap
    assert compute_time_overlap(0.0, 5.0, 10.0, 15.0) == 0.0


def test_merge_and_dedup():
    local = [
        ScoredChunk(text="Chunk A", start_time=0.0, end_time=10.0, similarity=0.7, source="local"),
    ]
    global_chunks = [
        # Duplicate of Chunk A (overlap 100%) but with lower base similarity
        ScoredChunk(text="Chunk A", start_time=0.0, end_time=10.0, similarity=0.6, source="global"),
        ScoredChunk(text="Chunk B", start_time=20.0, end_time=30.0, similarity=0.8, source="global"),
    ]

    merged = merge_and_dedup(local, global_chunks, max_chunks=5)
    assert len(merged) == 2  # duplicate eliminated
    texts = [c.text for c in merged]
    assert "Chunk A" in texts
    assert "Chunk B" in texts


def test_rerank_for_explain():
    chunks = [
        ScoredChunk(text="Prerequisite", start_time=10.0, end_time=20.0, similarity=0.5, source="global"),
        ScoredChunk(text="Recent", start_time=80.0, end_time=95.0, similarity=0.5, source="global"),
        ScoredChunk(text="Future", start_time=200.0, end_time=210.0, similarity=0.5, source="global"),
    ]
    # Current time = 100s. Recent chunk (80s) should get the highest boost
    reranked = rerank_for_explain(chunks, current_time=100.0)
    assert reranked[0].text == "Recent"
    assert reranked[1].text == "Prerequisite"
    assert reranked[2].text == "Future"


def test_check_relevance_threshold():
    chunks = [
        ScoredChunk(text="A", start_time=0, end_time=10, similarity=0.2, source="global"),
    ]
    assert not check_relevance_threshold(chunks, min_similarity=0.35)

    chunks.append(ScoredChunk(text="B", start_time=10, end_time=20, similarity=0.6, source="global"))
    assert check_relevance_threshold(chunks, min_similarity=0.35)


# ── Prompts Tests ───────────────────────────────────────────────────────────


def test_detect_intent():
    assert detect_intent("where does he mention python?", None) == "lookup"
    assert detect_intent("I didn't understand this concept", None) == "explain_better"
    assert detect_intent("can you explain in simpler terms?", None) == "explain_better"
    assert detect_intent("any question", mode="simpler") == "explain_better"
    assert detect_intent("summarize this video", None) == "summarize"
    assert detect_intent("hello how are you", None) == "out_of_scope"


def test_build_standalone_question():
    history = [
        {"role": "user", "content": "What is an embedding?"},
        {"role": "assistant", "content": "An embedding is a dense numerical vector."},
    ]
    rewritten = build_standalone_question("Why is that useful?", history, "nearby transcript")
    assert "Regarding" in rewritten or "that" in rewritten


def test_build_prompts():
    sys_prompt = build_system_prompt("explain_better")
    assert "tutor" in sys_prompt.lower()

    user_prompt = build_user_prompt(
        question="Can you explain vectors?",
        intent="explain_better",
        current_time=65.0,
        current_context="Discussion about physics",
        relevant_chunks=[{"text": "Vectors have magnitude", "start_time": 60.0, "end_time": 70.0}],
        recent_history=[],
        video_summary="Intro to Math",
        previous_approaches=["analogy"],
    )
    assert "## QUESTION" in user_prompt
    assert "## CURRENT TIMESTAMP" in user_prompt
    assert "<VIDEO_DATA>" in user_prompt
    assert "analogy" in user_prompt

