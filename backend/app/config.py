"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class Settings:
    postgres_user: str | None
    postgres_password: str | None
    postgres_host: str
    postgres_port: int
    postgres_db: str | None
    serp_api_key: str | None
    ollama_base_url: str
    ollama_embedding_model: str
    ollama_chat_model: str
    embedding_dimension: int
    retrieval_candidates: int
    retrieval_limit: int
    proximity_weight: float
    api_host: str
    api_port: int

    @property
    def database_url(self) -> str:
        """Return a SQLAlchemy URL assembled without logging credentials."""
        from sqlalchemy.engine import URL

        return str(
            URL.create(
                drivername="postgresql+psycopg2",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            )
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        postgres_user=os.getenv("POSTGRES_USER"),
        postgres_password=os.getenv("POSTGRES_PASSWORD"),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB"),
        serp_api_key=(os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_API_KEY") or None),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        ollama_chat_model=os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b"),
        embedding_dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
        retrieval_candidates=int(os.getenv("RETRIEVAL_CANDIDATES", "24")),
        retrieval_limit=int(os.getenv("RETRIEVAL_LIMIT", "6")),
        proximity_weight=float(os.getenv("RETRIEVAL_PROXIMITY_WEIGHT", "0.2")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "12701")),
    )
