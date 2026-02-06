from sqlalchemy.orm import Session
from sqlalchemy import select
from api.v0.auth.models import RecoveryTokenRequest
from sqlalchemy.exc import IntegrityError
from core.security import new_sk, new_rk
from core.db.tables.recoverykey import RecoveryKey
from core.db.tables.secretkey import SecretKey
from fastapi import APIRouter, Depends, HTTPException, status
from src.core.db.session import get_db
from src.api.v0.auth.models import NewTokenRequest, NewTokenResponse

router = APIRouter(prefix="/auth")



@router.post("/new")
def new_user(
    new_token_request: NewTokenRequest,
    session: Session = Depends(get_db),
):
    username = new_token_request.username
    new_secret_key = new_sk()
    new_recovery_key = new_rk()

    new_secret_key_model = SecretKey(sk=new_secret_key, username=username)
    new_recovery_key_model = RecoveryKey(rk=new_recovery_key, username=username)

    try:
        session.add(new_secret_key_model)
        session.add(new_recovery_key_model)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists!",
        )

    return NewTokenResponse(sk=new_secret_key, rk=new_recovery_key)


@router.post("/recovery")
def refresh_token(
    recovery_token_request: RecoveryTokenRequest,
    session: Session = Depends(get_db),
):
    secret_key = recovery_token_request.sk
    recovery_key = recovery_token_request.rk

    sk_object = session.execute(
        select(SecretKey).where(SecretKey.sk == secret_key)
    ).scalar()
    rk_object = session.execute(
        select(RecoveryKey).where(RecoveryKey.rk == recovery_key)
    ).scalar()

    if not sk_object:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret Key not found",
        )

    if not rk_object:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recovery Key not found",
        )

    if sk_object.username != rk_object.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid recovery key!",
        )

    try:
        session.delete(sk_object)

        while True:
            new_secret_key = new_sk()
            existing_key = session.execute(
                select(SecretKey).where(SecretKey.sk == new_secret_key)
            ).scalar()
            if existing_key is None:
                break

        new_secret_key_model = SecretKey(sk=new_secret_key, username=sk_object.username)
        session.add(new_secret_key_model)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        )

    return NewTokenResponse(sk=new_secret_key, rk=recovery_key)
