from fastapi import APIRouter

router = APIRouter(prefix="/user")


@router.post("/new_post")
def create_user_post():
    pass


@router.get("/{username}/posts")
def get_user_posts(username: str):
    pass


@router.delete("posts/{post_id}")
def delete_user_post(username: str, post_id: int):
    pass
