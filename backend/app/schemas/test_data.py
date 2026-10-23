from pydantic import BaseModel, Field, HttpUrl


class VideoCaptureRequest(BaseModel):
    """Video state captured when a user submits the extension chat form."""

    video_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    video_duration: float | None = Field(default=None, ge=0)
    current_timestep: float = Field(ge=0)
    is_playing: bool
    message: str = Field(min_length=1, max_length=5_000)


class VideoCaptureResponse(BaseModel):
    file_name: str
    transcript_status: str
    transcript_chunk_count: int
