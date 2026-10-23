# YouTube Tutor

## Project context

This project is planned as a YouTube learning assistant with:

- A Chrome Manifest V3 extension built with React and Vite.
- A FastAPI backend that processes transcripts and answers questions.
- SQLite persistence and an Ollama-backed language model.

The current workspace contains a project outline in `xd.txt`; it does not yet contain the application source, dependency manifests, or a README. Treat the outline as intended structure, not proof that a component or behavior already exists. Check the actual files before changing code or suggesting commands.

## Intended layout

- `extension/`: browser extension UI, content script, service worker, and API client.
- `backend/app/api/`: FastAPI routes and request dependencies.
- `backend/app/services/`: transcript, chunking, topic, embedding, retrieval, and chat logic.
- `backend/app/db/`: SQLite connection and repositories.
- `backend/app/llm/`: Ollama client.
- `backend/tests/`: backend tests.

## Working guidelines

- Follow existing patterns and keep changes focused on the requested behavior.
- Preserve the separation between extension UI, backend API, services, and persistence.
- Validate inputs at API boundaries and keep secrets in environment configuration; never commit credentials.
- Use the actual package scripts and test instructions found in the repository. Do not invent commands or assume dependencies are installed.
- Update relevant tests and documentation when implementing behavior.
