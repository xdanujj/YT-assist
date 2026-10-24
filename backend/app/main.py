from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.test_data import router as test_data_router

app = FastAPI(title="YouTube Tutor API")

# The extension is loaded with a unique chrome-extension:// origin in each browser profile.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost",
    "http://127.0.0.1",
    "https://www.youtube.com",
    "https://youtu.be",
],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(test_data_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
