"""Abstract provider interfaces for the YouTube Tutor backend."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    """A single timestamped segment of a video transcript."""

    text: str
    start: float  # seconds
    end: float  # seconds


class TranscriptNotAvailable(Exception):
    """Raised when no transcript can be fetched."""

    def __init__(self, video_id: str, reason: str = ""):
        self.video_id = video_id
        self.reason = reason
        super().__init__(f"Transcript not available for {video_id}: {reason}")


class TranscriptProvider(ABC):
    """Interface for fetching YouTube video transcripts."""

    @abstractmethod
    async def fetch_transcript(self, video_id: str) -> list[TranscriptSegment]:
        """Fetch timestamped transcript for a YouTube video.

        Args:
            video_id: The YouTube video ID.

        Returns:
            List of TranscriptSegment with text, start, and end times.

        Raises:
            TranscriptNotAvailable: If the transcript cannot be fetched.
        """
        ...

    @abstractmethod
    async def fetch_video_metadata(self, video_id: str) -> dict:
        """Return metadata dict with at least 'title' and 'duration_seconds'.

        Args:
            video_id: The YouTube video ID.

        Returns:
            Dict with at least 'title' (str | None) and 'duration_seconds' (float | None).
        """
        ...


class LLMProvider(ABC):
    """Interface for large language model text generation."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate a complete response.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.

        Returns:
            The generated text response.
        """
        ...

    @abstractmethod
    async def generate_stream(self, prompt: str, system: str | None = None):
        """Async generator yielding response tokens as strings.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.

        Yields:
            Individual token strings as they are generated.
        """
        ...


class EmbeddingProvider(ABC):
    """Interface for generating text embeddings."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (list of floats), one per input text.
        """
        ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A single embedding vector.
        """
        ...
