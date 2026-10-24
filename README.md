# YouTube Tutor — Test Extension

This proof-of-concept Chrome extension displays a temporary chat panel on the right side of a YouTube video's page. Pressing **Enter** in that panel sends the current video state to the local FastAPI backend. The backend fetches the public YouTube transcript and saves the result under `backend/test_data/<video_id>.json`.

## Captured data

Each Enter submission saves:

- `video_id`
- `title`
- `url`
- `video_duration` (seconds)
- `current_timestep` (seconds at the moment Enter is pressed)
- `is_playing`
- submitted chat `message`
- public transcript chunks, where YouTube makes captions available

The JSON file retains all chat events for the same video in `chat_events`. Transcript errors are stored as status text; unavailable captions do not block video-data capture. Transcripts are fetched from SerpApi's YouTube Video Transcript API using the video ID received from the extension.

## Setup

### 1. Install backend dependencies

From the repository root:

```powershell
py -m pip install -r backend/requirements.txt
```

### 2. Start the backend

Add your SerpApi private key to `backend/.env` as `SERP_API_KEY=...`. The backend loads that file on startup; keep it private and do not commit it. `SERPAPI_API_KEY` is also accepted.

From the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path backend)
py -m uvicorn app.main:app --host 127.0.0.1 --reload --port 12701
```

Verify it is running:

```powershell
Invoke-WebRequest http://127.0.0.1:12701/health
```

### 3. Load the unpacked extension

1. Open `chrome://extensions` in Chrome.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose the `D:\YT-assist-1\extension` folder. Choose this folder itself, not `extension/public`.
5. Open or refresh a normal YouTube video page.

A **YouTube Tutor — test chat** panel appears at the upper right. Type any test message and press Enter to write a capture JSON file.

## Notes

- The extension only works with the local FastAPI server at `http://127.0.0.1:12701`.
- JSON captures are ignored by Git to prevent transcript data from being committed.
- Transcript retrieval requires a valid SerpApi key in `backend/.env` (`SERP_API_KEY`) and uses SerpApi's YouTube Video Transcript engine.
