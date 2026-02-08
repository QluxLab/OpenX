from fastapi import APIRouter
from src.api.v0.auth.main import router as auth_router
from src.api.v0.media.main import router as media_router
from src.api.cdn import router as cdn_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(media_router)
router.include_router(cdn_router)