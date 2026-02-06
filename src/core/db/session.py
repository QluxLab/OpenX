from sqlalchemy import select
from src.core.db.tables.secretkey import SecretKey
from fastapi import Header, Depends, HTTPException, status
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

def get_current_user(
    authorization: str = Header(..., alias="X-Secret-Key"),
    session: Session = Depends(get_db),
) -> SecretKey:
    """Dependency to authenticate user via secret key"""
    sk_object = session.execute(
        select(SecretKey).where(SecretKey.sk == authorization)
    ).scalar()

    if not sk_object:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret key"
        )

    return sk_object
