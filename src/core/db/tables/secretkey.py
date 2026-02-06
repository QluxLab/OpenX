from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from core.db.tables.base import Base
class SecretKey(Base):
    __tablename__ = "secret_key"

    sk: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30))
    
    