from sqlalchemy import select
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.branch import Branch
from sqlalchemy.orm import Session
from src.core.db.session import get_current_user, get_db
from src.core.db.tables.secretkey import SecretKey
from src.core.logger import get_logger
from src.api.v0.user.models import PostCreateUnion, get_post_model, get_response_schema, TextPostUpdate, ImagePostUpdate, VideoPostUpdate, PostResponseUnion
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/user")
logger = get_logger(__name__)


def get_post_or_404(session, post_id):
    post = session.execute(select(UserPost).where(UserPost.id == post_id)).scalar()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post


def validate_branch_exists(session: Session, branch_name: str) -> None:
    """Validate that a branch exists, raise 404 if not"""
    branch = session.execute(
        select(Branch).where(Branch.name == branch_name)
    ).scalar()

    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )


@router.post(
    "/posts/", response_model=PostResponseUnion, status_code=status.HTTP_201_CREATED
)
def create_user_post(
    post_data: PostCreateUnion,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    model_class = get_post_model(post_data.type)

    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown post type: {post_data.type}",
        )

    # Extract to_branch and map it to branch column
    post_dict = post_data.model_dump()
    to_branch = post_dict.pop('to_branch', None)
    
    # Validate branch exists if posting to a branch
    if to_branch is not None:
        validate_branch_exists(session, to_branch)
    
    post = model_class(
        **post_dict,
        username=current_user.username,
        branch=to_branch,  # None means user profile, string means specific branch
    )

    session.add(post)
    session.commit()
    session.refresh(post)

    return get_response_schema(post)

@router.patch("/posts/{post_id}/", response_model=PostResponseUnion)
def update_post(
    post_id: int,
    post_data: TextPostUpdate | ImagePostUpdate | VideoPostUpdate,
    session: Session = Depends(get_db),
    current_user: SecretKey = Depends(get_current_user),
) -> PostResponseUnion:
    """
    Update a post partially.
    """
    post = get_post_or_404(session, post_id)

    if post.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this post",
        )

    update_data = post_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    session.commit()
    session.refresh(post)

    return get_response_schema(post)

@router.get("/{username}/posts/", response_model=list[PostResponseUnion])
def get_user_posts(
    username: str,
    post_type: str | None = None,
    include_branch_posts: bool = False,
    session: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Get posts from a user's profile.

    Args:
        username: The username to get posts for
        post_type: Filter by post type (text, image, video)
        include_branch_posts: If True, includes posts made to branches. If False (default), only profile posts
        skip: Number of posts to skip (pagination)
        limit: Maximum number of posts to return (max 500)
    """
    # Cap limit to prevent abuse
    limit = min(max(1, limit), 500)

    model_class = get_post_model(post_type) if post_type else UserPost

    if post_type and not model_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown post type: {post_type}",
        )

    query = select(model_class).where(model_class.username == username)

    if not include_branch_posts:
        # Only get profile posts (where branch is None)
        query = query.where(model_class.branch.is_(None))

    posts = (
        session.execute(
            query
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    return [get_response_schema(post) for post in posts]


@router.get("/posts/{post_id}/")
def get_post_by_id(
    post_id: int,
    session: Session = Depends(get_db),
    current_user: SecretKey = Depends(get_current_user),
):
    post = get_post_or_404(session, post_id)

    if post.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this post",
        )

    return get_response_schema(post)

@router.delete("/posts/{post_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    session: Session = Depends(get_db),
    current_user: SecretKey = Depends(get_current_user),
):
    post = get_post_or_404(session, post_id)

    if post.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this post",
        )
    session.delete(post)
    session.commit()
