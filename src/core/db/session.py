from sqlalchemy import select
from src.core.db.tables.secretkey import SecretKey
from fastapi import Header, Depends, HTTPException, status
from typing import Generator
from sqlalchemy.orm import sessionmaker, Session
from src.core.db.engine import engine
from src.core.security import verify_key

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
    # Extract key ID (first 16 chars) for lookup
    sk_id = authorization[:16] if len(authorization) >= 16 else authorization

    sk_object = session.execute(
        select(SecretKey).where(SecretKey.sk_id == sk_id)
    ).scalar()

    if not sk_object:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret key"
        )

    # Verify the full key against the hash
    if not verify_key(authorization, sk_object.sk_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret key"
        )

    return sk_object
