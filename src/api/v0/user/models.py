from src.core.db.tables.userpost import TextPost, ImagePost, VideoPost, UserPost
from datetime import datetime
from typing import Literal
from pydantic import Field, BaseModel, field_validator


# Allowed URL schemes to prevent XSS via javascript: and data: URLs
ALLOWED_URL_SCHEMES = {'http', 'https', ''}


def validate_url_scheme(url: str | None, field_name: str) -> str | None:
    """
    Validate that a URL uses only allowed schemes (http, https, or relative).

    This prevents stored XSS attacks via javascript: and data: URL schemes.
    """
    if url is None or url == '':
        return url

    # Extract scheme by finding the first ':' or returning empty
    scheme = ''
    if ':' in url:
        scheme = url.split(':', 1)[0].lower().strip()

    if scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"{field_name} must use http://, https://, or be a relative URL. "
            f"'{scheme}:' scheme is not allowed."
        )

    return url



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

    @field_validator('image_url')
    @classmethod
    def validate_image_url_scheme(cls, v: str) -> str:
        return validate_url_scheme(v, 'image_url')


class VideoPostCreate(PostBase):
    """Request schema for creating video posts"""

    type: Literal["video"] = "video"
    video_url: str = Field(..., max_length=512)
    thumbnail_url: str | None = Field(None, max_length=512)
    duration_seconds: int | None = Field(None, ge=0)

    @field_validator('video_url')
    @classmethod
    def validate_video_url_scheme(cls, v: str) -> str:
        return validate_url_scheme(v, 'video_url')

    @field_validator('thumbnail_url')
    @classmethod
    def validate_thumbnail_url_scheme(cls, v: str | None) -> str | None:
        return validate_url_scheme(v, 'thumbnail_url')




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

    @field_validator('image_url')
    @classmethod
    def validate_image_url_scheme(cls, v: str | None) -> str | None:
        return validate_url_scheme(v, 'image_url')


class VideoPostUpdate(PostUpdate):
    """Update schema for video posts"""

    video_url: str | None = Field(None, max_length=512)
    thumbnail_url: str | None = Field(None, max_length=512)
    duration_seconds: int | None = Field(None, ge=0)

    @field_validator('video_url')
    @classmethod
    def validate_video_url_scheme(cls, v: str | None) -> str | None:
        return validate_url_scheme(v, 'video_url')

    @field_validator('thumbnail_url')
    @classmethod
    def validate_thumbnail_url_scheme(cls, v: str | None) -> str | None:
        return validate_url_scheme(v, 'thumbnail_url')


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