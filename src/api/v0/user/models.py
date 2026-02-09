from src.core.db.tables.userpost import TextPost, ImagePost, VideoPost, UserPost
from datetime import datetime
from typing import Literal
from pydantic import Field, BaseModel



class PostBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=4096)
    to_branch: str | None = Field(None, max_length=256, description="Target branch name; None means user profile")

class TextPostCreate(PostBase):
    """Request schema for creating text posts"""

    type: Literal["text"] = "text"
    formatting: str | None = Field(None, max_length=50)


class ImagePostCreate(PostBase):
    """Request schema for creating image posts"""

    type: Literal["image"] = "image"
    image_url: str = Field(..., max_length=512)
    width: int | None = Field(None, gt=0)
    height: int | None = Field(None, gt=0)
    alt_text: str | None = Field(None, max_length=256)


class VideoPostCreate(PostBase):
    """Request schema for creating video posts"""

    type: Literal["video"] = "video"
    video_url: str = Field(..., max_length=512)
    thumbnail_url: str | None = Field(None, max_length=512)
    duration_seconds: int | None = Field(None, ge=0)




class PostUpdate(BaseModel):
    """Base update schema with optional common fields"""

    content: str | None = Field(None, min_length=1, max_length=4096)


class TextPostUpdate(PostUpdate):
    """Update schema for text posts"""

    formatting: str | None = None


class ImagePostUpdate(PostUpdate):
    """Update schema for image posts"""

    image_url: str | None = Field(None, max_length=512)
    width: int | None = Field(None, gt=0)
    height: int | None = Field(None, gt=0)
    alt_text: str | None = Field(None, max_length=256)


class VideoPostUpdate(PostUpdate):
    """Update schema for video posts"""

    video_url: str | None = Field(None, max_length=512)
    thumbnail_url: str | None = Field(None, max_length=512)
    duration_seconds: int | None = Field(None, ge=0)


class PostResponse(BaseModel):
    """Base response with common fields"""

    id: int
    type: str
    content: str
    branch: str | None = None  # Where the post actually lives
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TextPostResponse(PostResponse):
    """Response schema for text posts"""

    type: Literal["text"] = "text"
    formatting: str | None = None


class ImagePostResponse(PostResponse):
    """Response schema for image posts"""

    type: Literal["image"] = "image"
    image_url: str
    width: int | None = None
    height: int | None = None
    alt_text: str | None = None


class VideoPostResponse(PostResponse):
    """Response schema for video posts"""

    type: Literal["video"] = "video"
    video_url: str
    thumbnail_url: str | None = None
    duration_seconds: int | None = None

PostCreateUnion = TextPostCreate | ImagePostCreate | VideoPostCreate
PostResponseUnion = TextPostResponse | ImagePostResponse | VideoPostResponse

def get_post_model(post_type: str):
    """Map post type to SQLAlchemy model"""
    models = {
        "text": TextPost,
        "image": ImagePost,
        "video": VideoPost,
    }
    return models.get(post_type)


def get_response_schema(post: UserPost) -> PostResponseUnion:
    """Convert ORM model to appropriate response schema"""
    match post:
        case TextPost():
            return TextPostResponse.model_validate(post)
        case ImagePost():
            return ImagePostResponse.model_validate(post)
        case VideoPost():
            return VideoPostResponse.model_validate(post)
        case _:
            raise ValueError(f"Unknown post type: {post.type}")