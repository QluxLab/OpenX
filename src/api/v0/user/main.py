from sqlalchemy import select
from src.core.db.tables.userpost import UserPost
from sqlalchemy.orm import Session
from src.core.db.session import get_current_user, get_db
from src.core.db.tables.secretkey import SecretKey
from src.api.v0.user.models import PostCreateUnion, get_post_model, get_response_schema, TextPostUpdate, ImagePostUpdate, VideoPostUpdate, PostResponseUnion
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/user")



def get_post(session, post_id):
    post = session.execute(select(UserPost).where(UserPost.id == post_id)).scalar()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post

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

    post = model_class(
        **post_data.model_dump(),
        username=current_user.username,
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
    post = get_post(session,post_id)

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
    session: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    model_class = get_post_model(post_type) if post_type else UserPost

    if post_type and not model_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown post type: {post_type}",
        )

    posts = (
        session.execute(
            select(model_class)
            .where(model_class.username == username)
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
):
    post = get_post(session, post_id)

    return get_response_schema(post)

@router.delete("/posts/{post_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    session: Session = Depends(get_db),
    current_user: SecretKey = Depends(get_current_user),
):
    post = get_post(session, post_id)

    if post.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this post",
        )
    session.delete(post)
    session.commit()

