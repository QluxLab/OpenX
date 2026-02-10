"""
OpenX - Reddit-like social platform
Main FastAPI application with frontend serving
"""
import os
from pathlib import Path
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from src.core.db.session import get_db
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.branch import Branch
from src.core.db.tables.secretkey import SecretKey
from src.api.router import router as api_router
from src.api.rss import router as rss_router
from src.core.logger import configure_app_logging, get_logger
from src.core.middleware import (
    SecurityHeadersMiddleware,
    CSRFMiddleware,
    RequestLoggingMiddleware,
)

# Configure application logging
configure_app_logging(log_to_file=True)

# Get logger for this module
logger = get_logger(__name__)

# Base directory for templates and static files
BASE_DIR = Path(__file__).resolve().parent

# Create app with production settings
DEBUG = os.getenv("OPENX_DEBUG", "false").lower() == "true"
app = FastAPI(title="OpenX", debug=DEBUG)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RequestLoggingMiddleware)

logger.info("OpenX application initialized")

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=BASE_DIR / "frontend" / "templates")

# Include API routes
app.include_router(api_router)

# Include RSS routes (at root level, not under /api)
app.include_router(rss_router)


def get_current_user_optional(request: Request, session: Session = Depends(get_db)) -> dict | None:
    """Get current user from cookie if available"""
    sk = request.cookies.get("secret_key")
    if not sk:
        return None

    # Look up user by secret key (first 16 chars as ID)
    sk_id = sk[:16] if len(sk) >= 16 else sk
    user = session.execute(
        select(SecretKey).where(SecretKey.sk_id == sk_id)
    ).scalar()

    if user:
        # Verify the full key hash
        from src.core.security import verify_key
        if verify_key(sk, user.sk_hash):
            logger.debug(f"User authenticated: {user.username}")
            return {"username": user.username, "sk": sk}
    return None


# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def feed_page(
    request: Request,
    session: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Main feed page - shows all posts from all branches"""
    logger.info(f"Feed page accessed by user: {user['username'] if user else 'anonymous'}")

    # Get posts from all branches, ordered by most recent
    posts = session.execute(
        select(UserPost)
        .where(UserPost.branch.isnot(None))
        .order_by(desc(UserPost.id))
        .limit(50)
    ).scalars().all()

    # Get popular branches for sidebar
    branches = session.execute(
        select(Branch)
        .where(Branch.deleted_at.is_(None))
        .limit(10)
    ).scalars().all()

    return templates.TemplateResponse(
        "feed.html",
        {"request": request, "posts": posts, "branches": branches, "user": user}
    )


@app.get("/b/{branch_name}", response_class=HTMLResponse)
async def branch_page(
    request: Request,
    branch_name: str,
    session: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Branch (subreddit) page"""
    logger.info(f"Branch page accessed: /b/{branch_name}")

    # Get branch info
    branch = session.execute(
        select(Branch).where(
            Branch.name == branch_name,
            Branch.deleted_at.is_(None)
        )
    ).scalar()

    if not branch:
        logger.warning(f"Branch not found: {branch_name}")
        raise HTTPException(status_code=404, detail="Branch not found")

    # Get posts from this branch
    posts = session.execute(
        select(UserPost)
        .where(UserPost.branch == branch_name)
        .order_by(desc(UserPost.id))
        .limit(50)
    ).scalars().all()

    # Get popular branches for sidebar
    branches = session.execute(
        select(Branch)
        .where(Branch.deleted_at.is_(None))
        .limit(10)
    ).scalars().all()

    return templates.TemplateResponse(
        "branch.html",
        {"request": request, "posts": posts, "branch": branch, "branches": branches, "user": user}
    )


@app.get("/u/{username}", response_class=HTMLResponse)
async def user_page(
    request: Request,
    username: str,
    session: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """User profile page"""
    # Get user's posts (both profile and branch posts)
    posts = session.execute(
        select(UserPost)
        .where(UserPost.username == username)
        .order_by(desc(UserPost.id))
        .limit(50)
    ).scalars().all()

    # Get popular branches for sidebar
    branches = session.execute(
        select(Branch)
        .where(Branch.deleted_at.is_(None))
        .limit(10)
    ).scalars().all()

    return templates.TemplateResponse(
        "user.html",
        {"request": request, "posts": posts, "branches": branches, "profile_user": username, "user": user}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: dict | None = Depends(get_current_user_optional),
):
    """Login page"""
    if user:
        logger.info(f"Already authenticated user redirected from login: {user['username']}")
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@app.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: dict | None = Depends(get_current_user_optional),
):
    """Registration page"""
    if user:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("register.html", {"request": request, "user": None})


@app.get("/submit", response_class=HTMLResponse)
async def submit_page(
    request: Request,
    branch: str | None = None,
    user: dict | None = Depends(get_current_user_optional),
    session: Session = Depends(get_db),
):
    """Submit new post page"""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Default to user's profile branch if no branch specified
    if not branch:
        branch = f"u_{user['username']}"

    # Get branches for dropdown
    branches = session.execute(
        select(Branch)
        .where(Branch.deleted_at.is_(None))
        .order_by(Branch.name)
    ).scalars().all()

    return templates.TemplateResponse(
        "submit.html",
        {"request": request, "branches": branches, "selected_branch": branch, "user": user}
    )


@app.get("/create-branch", response_class=HTMLResponse)
async def create_branch_page(
    request: Request,
    user: dict | None = Depends(get_current_user_optional),
):
    """Create branch page"""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("create_branch.html", {"request": request, "user": user})


@app.get("/post/{post_id}", response_class=HTMLResponse)
async def post_detail_page(
    request: Request,
    post_id: int,
    session: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Post detail page with comments"""
    # Get post
    post = session.execute(
        select(UserPost).where(UserPost.id == post_id)
    ).scalar()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Get popular branches for sidebar
    branches = session.execute(
        select(Branch)
        .where(Branch.deleted_at.is_(None))
        .limit(10)
    ).scalars().all()

    return templates.TemplateResponse(
        "post.html",
        {"request": request, "post": post, "branches": branches, "user": user}
    )
