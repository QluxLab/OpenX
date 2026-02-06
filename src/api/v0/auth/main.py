from fastapi.requests import Request
from fastapi import APIRouter
router = APIRouter(prefix="/api")

@router.post("/new")
def new_user():
    pass # generate Secret key sk-*** and rotate key rk-***

@router.post("/rotate")
def refresh_token():
    pass 
