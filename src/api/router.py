from fastapi import APIRouter
from src.api.v0.auth.main import router as auth_router
from src.api.v0.media.main import router as media_router
from src.api.v0.branch.main import router as branch_router
from src.api.v0.user.main import router as user_router
from src.api.v0.comment.main import router as comment_router
from src.api.cdn import router as cdn_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(media_router)
router.include_router(branch_router)
router.include_router(user_router)
router.include_router(comment_router)
router.include_router(cdn_router)