from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from src.core.db.tables.comment import Comment
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.secretkey import SecretKey
from src.core.db.session import get_db, get_current_user
from src.core.logger import get_logger
from src.api.v0.comment.models import (
    CommentCreate,
    CommentResponse,
    CommentWithReplies,
)

router = APIRouter(prefix="/comments")
logger = get_logger(__name__)


def get_post_or_404(session: Session, post_id: int) -> UserPost:
    post = session.execute(select(UserPost).where(UserPost.id == post_id)).scalar()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post


def get_comment_or_404(session: Session, comment_id: int) -> Comment:
    comment = session.execute(select(Comment).where(Comment.id == comment_id)).scalar()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    return comment


def build_comment_tree(comments: list[Comment]) -> list[CommentWithReplies]:
    """Build nested comment tree from flat list"""
    comment_map = {}
    root_comments = []

    # First pass: create response objects
    for comment in comments:
        comment_map[comment.id] = CommentWithReplies(
            id=comment.id,
            post_id=comment.post_id,
            username=comment.username,
            content=comment.content,
            parent_id=comment.parent_id,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            replies=[]
        )

    # Second pass: build tree
    for comment in comments:
        node = comment_map[comment.id]
        if comment.parent_id is None:
            root_comments.append(node)
        elif comment.parent_id in comment_map:
            comment_map[comment.parent_id].replies.append(node)

    return root_comments


@router.post("/{post_id}", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment_for_post(
    post_id: int,
    comment_data: CommentCreate,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Create a comment on a specific post"""
    post = get_post_or_404(session, post_id)

    # If replying to another comment, verify it exists and belongs to same post
    if comment_data.parent_id:
        parent = get_comment_or_404(session, comment_data.parent_id)
        if parent.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent comment must belong to the same post",
            )

    comment = Comment(
        post_id=post_id,
        username=current_user.username,
        content=comment_data.content,
        parent_id=comment_data.parent_id,
    )

    session.add(comment)
    session.commit()
    session.refresh(comment)

    logger.info(f"Comment created on post {post_id} by {current_user.username}")

    return comment


@router.get("/{post_id}", response_model=list[CommentWithReplies])
def get_comments_for_post(
    post_id: int,
    session: Session = Depends(get_db),
):
    """Get all comments for a post as a tree"""
    get_post_or_404(session, post_id)

    comments = session.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
    ).scalars().all()

    return build_comment_tree(comments)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Delete a comment (must be the author)"""
    comment = get_comment_or_404(session, comment_id)

    if comment.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this comment",
        )

    session.delete(comment)
    session.commit()

    logger.info(f"Comment {comment_id} deleted by {current_user.username}")
