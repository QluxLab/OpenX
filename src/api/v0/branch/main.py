from fastapi import APIRouter

router = APIRouter(prefix="/branch")


@router.post("/create")
def new_branch():
    pass


@router.post("/{branch}/new_post")
def create_branch_post(branch: str):
    pass


@router.get("/{branch}/posts")
def get_branch_posts(branch: str):
    pass


@router.delete("/{branch}/posts/{post_id}")
def delete_branch_post(branch: str, post_id: int):
    pass
