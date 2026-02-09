from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.core.db.tables.base import Base
from datetime import datetime, timezone


class RecoveryKey(Base):
    """
    Stores hashed recovery keys for account recovery.
    
    Security design:
    - rk_id: First 8 chars of the original key used as a lookup identifier
    - rk_hash: Bcrypt hash of the full recovery key
    - username: Associated username
    - created_at: Timestamp for key rotation tracking
    """
    __tablename__ = "recovery_key"

    rk_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    rk_hash: Mapped[str] = mapped_column(String(256))
    username: Mapped[str] = mapped_column(String(256), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
