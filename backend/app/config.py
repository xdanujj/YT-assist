"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings for the YouTube Tutor backend, read from .env."""

    model_config = SettingsConfigDict(env_file=".env")

    # Database
    database_url: str = "postgresql+psycopg://tutor:your_password@localhost:5432/youtube_tutor"

    # External APIs
    serpapi_key: str = "your_serpapi_key_here"
    ollama_url: str = "http://localhost:11434"

    # LLM / Embedding models
    llm_model: str = "llama3.1:8b"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    # Chunking
    chunk_target_tokens: int = 400
    chunk_overlap_ratio: float = 0.12

    # Retrieval
    local_window_sec: int = 120
    global_top_k: int = 5
    final_chunks: int = 6
    min_similarity: float = 0.35

    # CORS / Chrome extension
    extension_origin: str = "chrome-extension://your_extension_id"

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
