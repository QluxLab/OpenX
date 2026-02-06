from typing import Generator
from sqlalchemy.orm import sessionmaker, Session
from src.core.db.engine import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
