from __future__ import annotations

from app.config import get_settings
from app.llm.ollama_client import OllamaClient, OllamaError


class EmbeddingError(RuntimeError):
    pass


def create_embeddings(texts: list[str], client: OllamaClient | None = None) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    try:
        vectors = (client or OllamaClient()).embed(texts, settings.ollama_embedding_model)
    except OllamaError as exc:
        raise EmbeddingError("Embedding service is unavailable") from exc

    if len(vectors) != len(texts):
        raise EmbeddingError("Embedding service returned the wrong number of vectors")
    for vector in vectors:
        if len(vector) != settings.embedding_dimension:
            raise EmbeddingError(
                f"Embedding dimension must be {settings.embedding_dimension}; received {len(vector)}"
            )
        if not all(isinstance(value, (int, float)) for value in vector):
            raise EmbeddingError("Embedding contains non-numeric values")
    return [[float(value) for value in vector] for vector in vectors]
