from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.tables.base import Base


class UserPost(Base):
    """Base class for all post types"""

    __tablename__ = "user_post"

    type: Mapped[str] = mapped_column(String(50))

    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    username: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(String(4096))
    
    # Branch field - None means post belongs to user's profile
    branch: Mapped[str | None] = mapped_column(String(256), nullable=True, default=None, index=True)

    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __mapper_args__ = {
        "polymorphic_on": "type",
        "polymorphic_identity": "base",
    }


class TextPost(UserPost):
    """Text-only post"""

    __mapper_args__ = {
        "polymorphic_identity": "text",
    }


class ImagePost(UserPost):
    """Image post"""

    __mapper_args__ = {
        "polymorphic_identity": "image",
    }

    @property
    def image(self) -> str | None:
        return self.image_url


class VideoPost(UserPost):
    """Video post"""

    __mapper_args__ = {
        "polymorphic_identity": "video",
    }

    @property
    def video(self) -> str | None:
        return self.video_url
