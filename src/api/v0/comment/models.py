from pydantic import BaseModel, Field
from datetime import datetime


class CommentCreate(BaseModel):
    post_id: int = Field(..., description="ID of the post to comment on")
    content: str = Field(..., min_length=1, max_length=4096)
    parent_id: int | None = Field(None, description="ID of parent comment for replies")


class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4096)


class CommentResponse(BaseModel):
    id: int
    post_id: int
    username: str
    content: str
    parent_id: int | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class CommentWithReplies(CommentResponse):
    replies: list["CommentWithReplies"] = []


# Allow self-referential model
CommentWithReplies.model_rebuild()
