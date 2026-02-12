from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from slowapi import Limiter

from src.core.security import new_sk, new_rk, hash_key, verify_key, new_branch_master_key, hash_master_key
from src.core.rate_limit import get_real_client_ip
from src.core.db.tables.recoverykey import RecoveryKey
from src.core.db.tables.secretkey import SecretKey
from src.core.db.tables.branch import Branch
from src.core.db.session import get_db
from src.core.logger import get_logger
from src.api.v0.auth.models import (
    NewTokenRequest,
    NewTokenResponse,
    RecoveryTokenRequest,
    VerifyLoginRequest,
    VerifyLoginResponse,
)

# Initialize logger
logger = get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_real_client_ip)

router = APIRouter(prefix="/auth")


def extract_key_id(key: str) -> str:
    """
    Extract the key identifier from a key for database lookup.
    Uses the first 16 characters (prefix + 8 chars of random part).
    """
    return key[:16] if len(key) >= 16 else key


@router.post("/new")
@limiter.limit("5/minute")
def new_user(
    request: Request,
    response: Response,
    new_token_request: NewTokenRequest,
    session: Session = Depends(get_db),
):
    """
    Create a new user with secure credential storage.

    Rate limited to 5 requests per minute per IP.
    Credentials are hashed before storage - only the user receives plaintext keys.
    Sets an HttpOnly cookie for secure authentication.
    """
    username = new_token_request.username
    logger.info(f"New user registration attempt: {username}")

    # Check if username already exists
    existing_sk = session.execute(
        select(SecretKey).where(SecretKey.username == username)
    ).scalar()

    if existing_sk:
        logger.warning(f"Registration failed - username already exists: {username}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists!",
        )

    # Generate new keys
    new_secret_key = new_sk()
    new_recovery_key = new_rk()

    # Hash keys before storing (only store hashes, never plaintext)
    sk_hash = hash_key(new_secret_key)
    rk_hash = hash_key(new_recovery_key)

    # Extract key IDs for database lookup
    sk_id = extract_key_id(new_secret_key)
    rk_id = extract_key_id(new_recovery_key)

    # Create database models with hashed credentials
    new_secret_key_model = SecretKey(
        sk_id=sk_id,
        sk_hash=sk_hash,
        username=username
    )
    new_recovery_key_model = RecoveryKey(
        rk_id=rk_id,
        rk_hash=rk_hash,
        username=username
    )

    # Create user's personal branch (u/username)
    branch_name = f"u_{username}"
    master_key = new_branch_master_key()
    hashed_master_key = hash_master_key(master_key)

    user_branch = Branch(
        name=branch_name,
        description=f"{username}'s personal profile",
        master_key=hashed_master_key,
        created_by=username,
    )

    try:
        session.add(new_secret_key_model)
        session.add(new_recovery_key_model)
        session.add(user_branch)
        session.commit()
        logger.info(f"User created successfully: {username}")
    except IntegrityError:
        session.rollback()
        logger.error(f"Database integrity error during user creation: {username}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists!",
        )

    # Set HttpOnly cookie for secure authentication (matches login flow)
    # HttpOnly prevents JavaScript access (XSS protection)
    # Secure flag should be enabled in production (HTTPS only)
    # SameSite=Strict prevents CSRF attacks
    response.set_cookie(
        key="secret_key",
        value=new_secret_key,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=365 * 24 * 60 * 60,  # 1 year in seconds
        path="/",
    )

    # Return plaintext keys to user (only time they're available)
    return NewTokenResponse(sk=new_secret_key, rk=new_recovery_key)


@router.post("/recovery")
@limiter.limit("3/minute")
def refresh_token(
    request: Request,
    recovery_token_request: RecoveryTokenRequest,
    session: Session = Depends(get_db),
):
    """
    Refresh a secret key using recovery key.
    
    Rate limited to 3 requests per minute per IP.
    Uses constant-time comparison to prevent timing attacks.
    """
    secret_key = recovery_token_request.sk
    recovery_key = recovery_token_request.rk
    
    # Extract key IDs for lookup
    sk_id = extract_key_id(secret_key)
    rk_id = extract_key_id(recovery_key)
    
    # Fetch both keys in a single operation to prevent timing attacks
    sk_object = session.execute(
        select(SecretKey).where(SecretKey.sk_id == sk_id)
    ).scalar()
    rk_object = session.execute(
        select(RecoveryKey).where(RecoveryKey.rk_id == rk_id)
    ).scalar()
    
    # Perform all validations before returning any error
    # This prevents timing attacks by not revealing which credential failed
    sk_valid = False
    rk_valid = False
    username_match = False
    
    if sk_object:
        sk_valid = verify_key(secret_key, sk_object.sk_hash)
    
    if rk_object:
        rk_valid = verify_key(recovery_key, rk_object.rk_hash)
    
    if sk_object and rk_object:
        username_match = sk_object.username == rk_object.username
    
    # Single error response for all validation failures (prevents information leakage)
    if not (sk_valid and rk_valid and username_match):
        logger.warning(f"Recovery failed - invalid credentials for sk_id: {sk_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    # Generate new secret key
    new_secret_key = new_sk()
    new_sk_id = extract_key_id(new_secret_key)
    new_sk_hash = hash_key(new_secret_key)
    
    try:
        # Update the existing secret key instead of delete + insert (fixes race condition)
        sk_object.sk_id = new_sk_id
        sk_object.sk_hash = new_sk_hash
        session.commit()
        logger.info(f"Secret key refreshed successfully for user: {sk_object.username}")
    except IntegrityError:
        session.rollback()
        logger.error(f"Database error during key refresh for user: {sk_object.username}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        )

    # Return new plaintext secret key (only time it's available)
    return NewTokenResponse(sk=new_secret_key, rk=recovery_key)


@router.post("/verify", response_model=VerifyLoginResponse)
@limiter.limit("10/minute")
def verify_login(
    request: Request,
    response: Response,
    verify_request: VerifyLoginRequest,
    session: Session = Depends(get_db),
):
    """
    Verify a secret key and return the associated username.

    Rate limited to 10 requests per minute per IP.
    Used for login verification.
    Sets an HttpOnly cookie for secure authentication.
    """
    sk_id = extract_key_id(verify_request.sk)

    sk_object = session.execute(
        select(SecretKey).where(SecretKey.sk_id == sk_id)
    ).scalar()

    if not sk_object:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_key(verify_request.sk, sk_object.sk_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Set HttpOnly cookie for secure authentication
    # HttpOnly prevents JavaScript access (XSS protection)
    # Secure flag should be enabled in production (HTTPS only)
    # SameSite=Strict prevents CSRF attacks
    response.set_cookie(
        key="secret_key",
        value=verify_request.sk,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=365 * 24 * 60 * 60,  # 1 year in seconds
        path="/",
    )

    logger.info(f"Login verified for user: {sk_object.username}")
    return VerifyLoginResponse(username=sk_object.username, valid=True)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
):
    """
    Logout by clearing the HttpOnly cookie.

    Since the cookie is HttpOnly, JavaScript cannot delete it directly.
    This endpoint clears the cookie server-side.
    """
    response.delete_cookie(
        key="secret_key",
        path="/",
    )
    logger.info("User logged out")
    return {"message": "Logged out successfully"}
