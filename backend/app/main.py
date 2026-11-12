"""Main FastAPI application entry point with lifespan and CORS configuration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings
from app.db.repo import VideoRepository, get_engine_and_session
from app.providers.ollama import OllamaEmbedding, OllamaLLM
from app.providers.serpapi import SerpApiTranscript
from app.services.chat import ChatService
from app.services.ingestion import IngestionService

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("youtube_tutor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for resource startup and graceful shutdown."""
    logger.info("Initializing YouTube Tutor Backend...")

    # Set up database engine and repository
    engine, session_factory = get_engine_and_session(settings.database_url)
    repo = VideoRepository(session_factory)

    # Instantiate external providers
    transcript_provider = SerpApiTranscript()
    llm_provider = OllamaLLM()
    embedding_provider = OllamaEmbedding()

    # Instantiate application services
    ingestion_service = IngestionService(
        repo=repo,
        transcript_provider=transcript_provider,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
    )
    chat_service = ChatService(
        repo=repo,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
    )

    # Store on app.state for FastAPI dependency injection
    app.state.repo = repo
    app.state.ingestion_service = ingestion_service
    app.state.chat_service = chat_service
    app.state.engine = engine

    logger.info("Application ready.")
    yield

    logger.info("Disposing database connections...")
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="YouTube Tutor API",
    description="Backend API for AI-assisted YouTube tutoring Chrome Extension",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration: allow Chrome extension origin and localhost
allowed_origins = [
    settings.extension_origin,
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    """Root status check."""
    return {
        "app": "YouTube Tutor API",
        "status": "running",
        "docs": "/docs",
    }

