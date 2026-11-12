"""Small Ollama HTTP client used by embedding and chat services."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.config import get_settings


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 120.0):
        self.base_url = (base_url or get_settings().ollama_base_url).rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise OllamaError(f"Ollama request failed: {type(exc).__name__}") from exc
        if not isinstance(body, dict):
            raise OllamaError("Ollama returned an invalid response")
        return body

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        settings = get_settings()
        result = self._post(
            "/api/embed",
            {"model": model or settings.ollama_embedding_model, "input": texts},
        )
        embeddings = result.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaError("Ollama returned an unexpected embedding count")
        if any(not isinstance(vector, list) for vector in embeddings):
            raise OllamaError("Ollama returned an invalid embedding")
        return embeddings

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        settings = get_settings()
        result = self._post(
            "/api/chat",
            {"model": model or settings.ollama_chat_model, "messages": messages, "stream": False},
        )
        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned an empty chat response")
        return content.strip()
