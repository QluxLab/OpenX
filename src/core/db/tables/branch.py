from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime

from src.core.db.tables.base import Base


class Branch(Base):
    """Branch (subreddit) table"""
    
    __tablename__ = "branch"

    name: Mapped[str] = mapped_column(String(256), primary_key=True, unique=True)
    description: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    master_key: Mapped[str] = mapped_column(String(256))
    created_by: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)