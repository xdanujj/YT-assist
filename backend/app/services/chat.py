"""Chat and query pipeline service."""

from __future__ import annotations

import logging
from typing import AsyncGenerator, List, Optional

from app.config import get_settings
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
    merge_and_dedup,
    rerank_for_explain,
)
from app.core.timestamps import (
    get_time_window,
    validate_timestamps_in_text,
)
from app.db.repo import VideoRepository
from app.providers.base import EmbeddingProvider, LLMProvider
from app.schemas import (
    AskResponseChunk,
    ChatMessage as ChatMessageSchema,
    ChunkInfo,
    ExplainMode,
    HistoryResponse,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates query processing, context retrieval, and response generation."""

    def __init__(
        self,
        repo: VideoRepository,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.repo = repo
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def get_history(self, video_id: str, session_id: str) -> HistoryResponse:
        """Fetch chat history for a given video and session."""
        db_messages = await self.repo.get_chat_history(video_id, session_id, limit=50)
        messages: List[ChatMessageSchema] = []
        for m in db_messages:
            chunks_used: Optional[List[ChunkInfo]] = None
            if m.chunks_used and isinstance(m.chunks_used, list):
                try:
                    chunks_used = [ChunkInfo(**c) for c in m.chunks_used]
                except Exception:
                    chunks_used = None

            messages.append(
                ChatMessageSchema(
                    role=m.role,
                    content=m.content,
                    timestamp=m.created_at,
                    chunks_used=chunks_used,
                )
            )
        return HistoryResponse(messages=messages)

    async def ask(
        self,
        video_id: str,
        question: str,
        session_id: str,
        current_time: float,
        mode: Optional[ExplainMode] = None,
    ) -> AsyncGenerator[AskResponseChunk, None]:
        """Execute the full query pipeline with SSE streaming.

        Yields:
            AskResponseChunk instances for tokens, completion, or error.
        """
        settings = get_settings()

        # Step 1: Ensure video exists and is ready
        video = await self.repo.get_video(video_id)
        if not video or video.status != "ready":
            err_msg = (
                f"Video {video_id} is not ready (status: {video.status if video else 'not registered'})."
            )
            yield AskResponseChunk(type="error", content=err_msg)
            return

        # Step 2: Intent detection
        mode_str = mode.value if mode else None
        intent = detect_intent(question, mode=mode_str)

        # Step 3: Fetch recent chat history
        db_history = await self.repo.get_chat_history(video_id, session_id, limit=6)
        history_dicts = [{"role": m.role, "content": m.content} for m in db_history]

        # Step 4: Local context (nearby transcript window)
        start_win, end_win = get_time_window(
            current_time, window_seconds=float(settings.local_window_sec)
        )
        local_segments = await self.repo.get_transcript_segments(
            video_id, start=start_win, end=end_win
        )
        current_context = " ".join(s.text for s in local_segments)

        # Step 5: Standalone question rewriting for follow-ups
        effective_question = question
        if history_dicts:
            lowered = question.lower()
            anaphoric_words = ("this", "that", "it", "they", "why is that", "what does that mean")
            if any(w in lowered for w in anaphoric_words):
                try:
                    rewrite_prompt = build_rewrite_prompt(
                        question=question,
                        history=history_dicts,
                        nearby_text=current_context[:300],
                    )
                    rewritten = await self.llm_provider.generate(
                        prompt=rewrite_prompt,
                        system="Rewrite the follow-up question into a standalone question. Output ONLY the rewritten question.",
                    )
                    if rewritten and len(rewritten.strip()) > 5:
                        effective_question = rewritten.strip()
                except Exception as exc:
                    logger.warning("LLM rewrite failed, using original: %s", exc)
                    effective_question = build_standalone_question(
                        question, history_dicts, current_context
                    )

        # Step 6: Multi-stage retrieval
        # 6a. Local chunks (around current_time)
        db_local_chunks = await self.repo.get_chunks_by_time_range(
            video_id, start=start_win, end=end_win
        )
        local_scored = [
            ScoredChunk(
                text=c.text,
                start_time=c.start_time,
                end_time=c.end_time,
                similarity=0.6,  # base baseline score for temporal proximity
                source="local",
            )
            for c in db_local_chunks
        ]

        # 6b. Global semantic search
        try:
            query_embedding = await self.embedding_provider.embed_single(effective_question)
            db_global_matches = await self.repo.search_similar_chunks(
                video_id=video_id,
                query_embedding=query_embedding,
                top_k=settings.global_top_k,
            )
            global_scored = [
                ScoredChunk(
                    text=c.text,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    similarity=sim,
                    source="global",
                )
                for c, sim in db_global_matches
            ]
        except Exception as exc:
            logger.error("Embedding or vector search failed: %s", exc)
            global_scored = []

        # 6c. Merge and deduplicate
        merged_chunks = merge_and_dedup(
            local_chunks=local_scored,
            global_chunks=global_scored,
            max_chunks=settings.final_chunks,
        )

        # 6d. Re-rank for explain_better
        if intent == "explain_better":
            merged_chunks = rerank_for_explain(merged_chunks, current_time=current_time)

        # Step 7: Guardrail check for lookup intent
        if intent == "lookup" and not check_relevance_threshold(
            merged_chunks, min_similarity=settings.min_similarity
        ):
            no_coverage_msg = (
                "The video doesn't seem to cover this topic, and no relevant transcript "
                "segments were found. Please ask something discussed in the video."
            )
            # Save interaction in history
            await self.repo.save_chat_message(
                video_pk=video.id,
                session_id=session_id,
                role="user",
                content=question,
                current_time=current_time,
                intent=intent,
            )
            await self.repo.save_chat_message(
                video_pk=video.id,
                session_id=session_id,
                role="assistant",
                content=no_coverage_msg,
                current_time=current_time,
                intent=intent,
                chunks_used=[],
            )
            yield AskResponseChunk(type="token", content=no_coverage_msg)
            yield AskResponseChunk(
                type="done", content=no_coverage_msg, chunks_used=[]
            )
            return

        # Step 8: Detect previously attempted explanation approaches
        previous_approaches: List[str] = []
        if intent == "explain_better":
            for h in history_dicts:
                content_lower = h.get("content", "").lower()
                if "analogy" in content_lower:
                    previous_approaches.append("analogy")
                if "step-by-step" in content_lower or "step 1" in content_lower:
                    previous_approaches.append("step-by-step")
                if "example" in content_lower:
                    previous_approaches.append("worked example")
                if "simple" in content_lower:
                    previous_approaches.append("simplified wording")
            previous_approaches = list(set(previous_approaches))

        # Step 9: Assemble prompt
        chunk_dicts = [
            {
                "text": c.text,
                "start_time": c.start_time,
                "end_time": c.end_time,
            }
            for c in merged_chunks
        ]
        system_prompt = build_system_prompt(intent)
        user_prompt = build_user_prompt(
            question=effective_question,
            intent=intent,
            current_time=current_time,
            current_context=current_context,
            relevant_chunks=chunk_dicts,
            recent_history=history_dicts,
            video_summary=video.summary or "",
            previous_approaches=previous_approaches if previous_approaches else None,
        )

        # Step 10: Stream generation from LLM
        tokens_received: List[str] = []
        try:
            async for token in self.llm_provider.generate_stream(
                prompt=user_prompt, system=system_prompt
            ):
                tokens_received.append(token)
                yield AskResponseChunk(type="token", content=token)
        except Exception as exc:
            logger.error("LLM streaming generation error: %s", exc, exc_info=True)
            yield AskResponseChunk(type="error", content=f"Generation error: {exc}")
            return

        full_response = "".join(tokens_received)

        # Step 11: Validate timestamps
        max_duration = video.duration_seconds or 86400.0  # default 24h if unknown
        validated_response = validate_timestamps_in_text(
            full_response, max_duration=max_duration
        )

        # Step 12: Record chunks used
        chunks_info = [
            ChunkInfo(
                text=c.text,
                start_time=c.start_time,
                end_time=c.end_time,
                similarity=round(c.similarity, 3),
            )
            for c in merged_chunks
        ]
        chunks_info_dicts = [c.model_dump() for c in chunks_info]

        # Step 13: Save user and assistant messages to database
        try:
            await self.repo.save_chat_message(
                video_pk=video.id,
                session_id=session_id,
                role="user",
                content=question,
                current_time=current_time,
                intent=intent,
            )
            await self.repo.save_chat_message(
                video_pk=video.id,
                session_id=session_id,
                role="assistant",
                content=validated_response,
                current_time=current_time,
                intent=intent,
                chunks_used=chunks_info_dicts,
            )
        except Exception as exc:
            logger.warning("Failed to persist chat message: %s", exc)

        # Step 14: Yield done
        yield AskResponseChunk(
            type="done",
            content=validated_response,
            chunks_used=chunks_info,
        )

