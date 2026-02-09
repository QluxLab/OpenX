from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from src.core.db.tables.base import Base


class Comment(Base):
    """Comment on a post"""

    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_post.id"), index=True)
    username: Mapped[str] = mapped_column(String(256), index=True)
    content: Mapped[str] = mapped_column(String(4096))
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("comment.id"), nullable=True, default=None, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )

    # Self-referential relationship for replies
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        backref="parent",
        remote_side=[id],
        foreign_keys=[parent_id]
    )
