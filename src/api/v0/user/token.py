from fastapi import APIRouter

router = APIRouter(prefix="/token")


@router.post("/new_token")
def new_token():
    pass


@router.post("/revoke_token")
def revoke_token():
    pass
