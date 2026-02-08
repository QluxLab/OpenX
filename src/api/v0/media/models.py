from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    """Response schema for successful media upload"""

    id: str = Field(..., description="Unique media identifier")
    url: str = Field(..., description="CDN URL for the uploaded media")
    media_type: Literal["image", "video"] = Field(..., description="Type of media")
    filename: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    created_at: datetime = Field(..., description="Upload timestamp")


class MediaListResponse(BaseModel):
    """Response schema for listing user's media"""

    id: str
    url: str
    media_type: Literal["image", "video"]
    filename: str
    size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True


class MediaDeleteResponse(BaseModel):
    """Response schema for media deletion"""

    id: str
    deleted: bool = True
    message: str = "Media deleted successfully"


# Allowed MIME types for media uploads
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/ogg",
}

ALLOWED_CONTENT_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES

# Max file sizes (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
