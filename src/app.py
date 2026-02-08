import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.router import router as api_router
from src.core.db.engine import engine
from src.core.db.tables.base import Base
# Import all models so they are registered with Base
from src.core.db.tables.secretkey import SecretKey
from src.core.db.tables.recoverykey import RecoveryKey
from src.core.db.tables.media import Media
from src.core.db.tables.branch import Branch
from src.core.db.tables.userpost import UserPost, TextPost, ImagePost, VideoPost
from src.core.db.tables.moderation_log import ModerationLog


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure .data directory exists for SQLite database
    db_dir = Path("./.data")
    db_dir.mkdir(parents=True, exist_ok=True)

    # Create database and tables on startup if not exists
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="OpenX", lifespan=lifespan)

# Include API routes
app.include_router(api_router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Rate limit exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
