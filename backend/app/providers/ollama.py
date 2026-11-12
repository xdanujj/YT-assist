"""Ollama-based LLM and embedding providers."""

import json
import logging

import httpx

from app.config import get_settings
from app.providers.base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 60.0  # seconds — generous for large completions
_EMBED_TIMEOUT = 30.0  # seconds


class OllamaLLM(LLMProvider):
    """LLM provider backed by a local Ollama instance."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_url.rstrip("/")
        self._model = settings.llm_model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a non-streaming generate request and return the full response text."""
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system is not None:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama generate request timed out after {_LLM_TIMEOUT}s")
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self._base_url}. Is it running?"
            )

        return data["response"]

    async def generate_stream(self, prompt: str, system: str | None = None):
        """Stream tokens from Ollama as an async generator.

        Each yielded value is a token string. The generator completes when
        Ollama signals `done: true`.
        """
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
        }
        if system is not None:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/api/generate",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning("Non-JSON line from Ollama stream: %s", line)
                            continue
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            return
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama streaming request timed out after {_LLM_TIMEOUT}s")
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self._base_url}. Is it running?"
            )


class OllamaEmbedding(EmbeddingProvider):
    """Embedding provider backed by a local Ollama instance."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_url.rstrip("/")
        self._model = settings.embed_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via Ollama's /api/embed endpoint."""
        payload = {
            "model": self._model,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=_EMBED_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/api/embed",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama embed request timed out after {_EMBED_TIMEOUT}s")
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama embed returned HTTP {exc.response.status_code}: {exc.response.text}"
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self._base_url}. Is it running?"
            )

        return data["embeddings"]

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text string and return its vector."""
        vectors = await self.embed([text])
        return vectors[0]
