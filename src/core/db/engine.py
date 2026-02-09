import os
from pathlib import Path
from sqlalchemy import create_engine

database_url = os.getenv("OPENX_DB_URL") or "sqlite:///.data/openx.db"

# Ensure the .data directory exists
data_dir = Path(".data")
data_dir.mkdir(exist_ok=True)

# Configure engine with connection pooling
# For SQLite, pool settings are mostly ignored but good practice for production DBs
engine = create_engine(
    database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create all tables on import
from src.core.db.tables.base import Base
from src.core.db.tables.secretkey import SecretKey
from src.core.db.tables.recoverykey import RecoveryKey
from src.core.db.tables.branch import Branch
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.media import Media
from src.core.db.tables.moderation_log import ModerationLog
from src.core.db.tables.comment import Comment

Base.metadata.create_all(engine)