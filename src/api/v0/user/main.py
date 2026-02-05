from fastapi import APIRouter

router = APIRouter(prefix="/user")


@router.post("/create")
def new_user():
    pass


@router.get("/{username}/new_token")
def create_user_token(username: str):
    pass


@router.delete("/{username}/revoke_token")
def revoke_user_token(username: str):
    pass


@router.post("/{username}/new_post")
def create_user_post(username: str):
    pass


@router.get("/{username}/posts")
def get_user_posts(username: str):
    pass


@router.delete("/{username}/posts/{post_id}")
def delete_user_post(username: str, post_id: int):
    pass
