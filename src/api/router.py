from fastapi import APIRouter
from src.api.v0.auth.main import router as auth_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)