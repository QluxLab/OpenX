"""
Branch API endpoints with moderation and audit capabilities.
"""
import json
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.core.db.session import get_current_user, get_db
from src.core.db.tables.secretkey import SecretKey
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.branch import Branch
from src.core.db.tables.moderation_log import ModerationLog, log_moderation_action
from src.core.security import (
    new_branch_master_key, 
    hash_master_key, 
    verify_master_key,
    hash_key,
)
from src.api.v0.user.models import PostCreateUnion, PostResponseUnion, get_post_model, get_response_schema
from src.api.v0.branch.models import (
    BranchCreate, 
    BranchResponse, 
    BranchCreateResponse, 
    BranchUpdate,
    PaginationParams,
    MasterKeyRotateResponse,
    BranchDeleteConfirm,
)

from slowapi import Limiter

from src.core.rate_limit import get_real_client_ip

limiter = Limiter(key_func=get_real_client_ip)

router = APIRouter(prefix="/branch")


def get_branch_or_404(session: Session, branch_name: str) -> Branch:
    """
    Get a branch by name or raise 404.
    Only returns non-deleted branches.
    """
    branch = session.execute(
        select(Branch).where(
            Branch.name == branch_name,
            Branch.deleted_at.is_(None)
        )
    ).scalar()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Branch '{branch_name}' does not exist",
        )
    return branch


def branch_exists(session: Session, branch_name: str) -> bool:
    """Check if a branch exists (and is not deleted)"""
    branch = session.execute(
        select(Branch).where(
            Branch.name == branch_name,
            Branch.deleted_at.is_(None)
        )
    ).scalar()
    return branch is not None


def get_key_hash_for_audit(master_key: str) -> str:
    """
    Create a consistent hash of the master key for audit purposes.
    Uses SHA-256 for fast, consistent hashing (not for verification).
    """
    return hashlib.sha256(master_key.encode()).hexdigest()[:16]


def verify_branch_moderator_secure(
    session: Session,
    branch_name: str,
    master_key: str
) -> Branch:
    """
    Verify the master key for a branch and return the branch if valid.
    Uses constant-time operations to prevent timing attacks.
    """
    branch = session.execute(
        select(Branch).where(
            Branch.name == branch_name,
            Branch.deleted_at.is_(None)
        )
    ).scalar()
    
    # Always perform key verification to prevent timing attacks
    if branch:
        is_valid = verify_master_key(master_key, branch.master_key)
    else:
        # Perform dummy hash check to prevent timing attacks
        verify_master_key(master_key, hash_master_key("dummy_key_for_timing"))
        is_valid = False
    
    if not is_valid or branch is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials",
        )
    
    return branch


def verify_branch_moderator_or_creator(
    session: Session,
    branch_name: str,
    master_key: str | None,
    current_user: SecretKey | None,
) -> Branch:
    """
    Verify access via master key OR branch creator.
    Allows branch creator to moderate their branch even if they lost the master key.
    """
    branch = session.execute(
        select(Branch).where(
            Branch.name == branch_name,
            Branch.deleted_at.is_(None)
        )
    ).scalar()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Branch '{branch_name}' does not exist",
        )
    
    # Allow creator access
    if current_user and current_user.username == branch.created_by:
        return branch
    
    # Otherwise require valid master key
    if master_key and verify_master_key(master_key, branch.master_key):
        return branch
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized",
    )


def get_branch_master_key(
    x_branch_master_key: str = Header(..., alias="X-Branch-Master-Key"),
) -> str:
    """Dependency to get master key from header"""
    return x_branch_master_key


def get_optional_master_key(
    x_branch_master_key: str | None = Header(None, alias="X-Branch-Master-Key"),
) -> str | None:
    """Dependency to get optional master key from header"""
    return x_branch_master_key


def get_request_info(request: Request) -> tuple[str | None, str | None]:
    """Extract IP address and user agent from request for audit logging"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return ip_address, user_agent


@router.post("/create", response_model=BranchCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def new_branch(
    request: Request,
    branch_data: BranchCreate,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Create a new branch.
    
    Returns the branch info including the master key (only shown once!).
    Store the master key securely - it's needed for branch moderation.
    
    Rate limited to 5 branches per hour per IP.
    """
    master_key = new_branch_master_key()
    hashed_master_key = hash_master_key(master_key)
    
    branch = Branch(
        name=branch_data.name,
        description=branch_data.description,
        master_key=hashed_master_key,
        created_by=current_user.username,
    )
    
    try:
        session.add(branch)
        session.commit()
        session.refresh(branch)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Branch '{branch_data.name}' already exists",
        )
    
    return BranchCreateResponse(
        name=branch.name,
        description=branch.description,
        master_key=master_key,
        created_by=branch.created_by,
        created_at=branch.created_at,
    )


@router.get("/{branch}", response_model=BranchResponse)
def get_branch_info(
    branch: str,
    session: Session = Depends(get_db),
):
    """Get branch information (public)"""
    branch_obj = get_branch_or_404(session, branch)
    return BranchResponse.model_validate(branch_obj)


@router.post("/{branch}/posts", response_model=PostResponseUnion, status_code=status.HTTP_201_CREATED)
@limiter.limit("100/hour")
def create_branch_post(
    request: Request,
    branch: str,
    post_data: PostCreateUnion,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Create a post in a specific branch.
    
    Rate limited to 100 posts per hour per IP.
    """
    get_branch_or_404(session, branch)
    
    model_class = get_post_model(post_data.type)
    
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown post type: {post_data.type}",
        )
    
    post_dict = post_data.model_dump()
    post_dict.pop('to_branch', None)
    
    post = model_class(
        **post_dict,
        username=current_user.username,
        branch=branch,
    )
    
    session.add(post)
    session.commit()
    session.refresh(post)
    
    return get_response_schema(post)


@router.get("/{branch}/posts", response_model=list[PostResponseUnion])
def get_branch_posts(
    branch: str,
    post_type: str | None = None,
    username: str | None = None,
    session: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
):
    """
    Get posts from a specific branch.
    
    Args:
        branch: The branch name to get posts from
        post_type: Filter by post type (text, image, video)
        username: Filter by specific username (optional)
        pagination: Pagination parameters (skip, limit - max 1000)
    """
    get_branch_or_404(session, branch)
    
    model_class = get_post_model(post_type) if post_type else UserPost
    
    if post_type and not model_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown post type: {post_type}",
        )
    
    query = select(model_class).where(model_class.branch == branch)
    
    if username:
        query = query.where(model_class.username == username)
    
    posts = (
        session.execute(
            query
            .offset(pagination.skip)
            .limit(pagination.limit)
        )
        .scalars()
        .all()
    )
    
    return [get_response_schema(post) for post in posts]


@router.delete("/{branch}/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch_post(
    branch: str,
    post_id: int,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Delete a post from a branch (must be the author)"""
    get_branch_or_404(session, branch)
    
    post = session.execute(
        select(UserPost)
        .where(UserPost.id == post_id)
        .where(UserPost.branch == branch)
    ).scalar()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found in this branch",
        )
    
    if post.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this post",
        )
    
    session.delete(post)
    session.commit()


# =====================
# MODERATION ENDPOINTS
# =====================

@router.delete("/{branch}/moderate/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
def moderate_delete_post(
    request: Request,
    branch: str,
    post_id: int,
    master_key: str = Depends(get_branch_master_key),
    session: Session = Depends(get_db),
):
    """
    Delete any post in a branch as a moderator.
    
    Requires the X-Branch-Master-Key header with the branch's master key.
    All moderation actions are logged for audit purposes.
    """
    branch_obj = verify_branch_moderator_secure(session, branch, master_key)
    
    post = session.execute(
        select(UserPost)
        .where(UserPost.id == post_id)
        .where(UserPost.branch == branch)
    ).scalar()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found in this branch",
        )
    
    ip_address, user_agent = get_request_info(request)
    log_moderation_action(
        session=session,
        branch=branch,
        action="delete_post",
        moderator_key_hash=get_key_hash_for_audit(master_key),
        target_id=str(post_id),
        target_type="post",
        details=json.dumps({"post_username": post.username, "post_type": post.type}),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    session.delete(post)
    session.commit()


@router.patch("/{branch}/moderate/settings", response_model=BranchResponse)
@limiter.limit("30/minute")
def moderate_update_branch(
    request: Request,
    branch: str,
    branch_data: BranchUpdate,
    master_key: str = Depends(get_branch_master_key),
    session: Session = Depends(get_db),
):
    """
    Update branch settings as a moderator.
    
    Requires the X-Branch-Master-Key header with the branch's master key.
    All moderation actions are logged for audit purposes.
    """
    branch_obj = verify_branch_moderator_secure(session, branch, master_key)
    
    old_values = {"description": branch_obj.description}
    
    update_data = branch_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(branch_obj, field, value)
    
    ip_address, user_agent = get_request_info(request)
    log_moderation_action(
        session=session,
        branch=branch,
        action="update_settings",
        moderator_key_hash=get_key_hash_for_audit(master_key),
        target_type="settings",
        details=json.dumps({"old": old_values, "new": update_data}),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    session.commit()
    session.refresh(branch_obj)
    
    return BranchResponse.model_validate(branch_obj)


@router.post("/{branch}/moderate/rotate-key", response_model=MasterKeyRotateResponse)
@limiter.limit("3/hour")
def rotate_master_key(
    request: Request,
    branch: str,
    master_key: str | None = Depends(get_optional_master_key),
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Rotate the master key for a branch.
    
    Requires either:
    - The current X-Branch-Master-Key header, OR
    - Authentication as the branch creator
    
    Returns the new master key (only shown once!).
    """
    branch_obj = verify_branch_moderator_or_creator(
        session=session,
        branch_name=branch,
        master_key=master_key,
        current_user=current_user,
    )
    
    new_key = new_branch_master_key()
    branch_obj.master_key = hash_master_key(new_key)
    
    ip_address, user_agent = get_request_info(request)
    log_moderation_action(
        session=session,
        branch=branch,
        action="rotate_key",
        moderator_key_hash=get_key_hash_for_audit(master_key) if master_key else f"creator:{current_user.username}",
        target_type="master_key",
        details=json.dumps({"rotated_by": current_user.username}),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    session.commit()
    
    return MasterKeyRotateResponse(
        name=branch_obj.name,
        master_key=new_key,
    )


@router.delete("/{branch}/moderate", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
def moderate_delete_branch(
    request: Request,
    branch: str,
    confirmation: BranchDeleteConfirm,
    master_key: str = Depends(get_branch_master_key),
    session: Session = Depends(get_db),
):
    """
    Delete a branch and all its posts as a moderator.
    
    Requires:
    - The X-Branch-Master-Key header with the branch's master key
    - A confirmation body with branch_name matching the URL and confirmation="DELETE"
    
    This is a soft delete - the branch can be recovered if needed.
    All moderation actions are logged for audit purposes.
    """
    if confirmation.branch_name != branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch name in confirmation does not match URL",
        )
    
    branch_obj = verify_branch_moderator_secure(session, branch, master_key)
    
    ip_address, user_agent = get_request_info(request)
    
    # Get post count for audit
    post_count = session.execute(
        select(UserPost).where(UserPost.branch == branch)
    ).scalars().all()
    post_count_num = len(post_count) if post_count else 0
    
    log_moderation_action(
        session=session,
        branch=branch,
        action="delete_branch",
        moderator_key_hash=get_key_hash_for_audit(master_key),
        target_type="branch",
        details=json.dumps({
            "post_count": post_count_num,
            "created_by": branch_obj.created_by,
        }),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Use bulk delete to prevent memory issues
    session.execute(
        delete(UserPost).where(UserPost.branch == branch)
    )
    
    # Soft delete the branch
    branch_obj.deleted_at = datetime.utcnow()
    
    session.commit()


# =====================
# AUDIT ENDPOINTS
# =====================

@router.get("/{branch}/moderate/audit", response_model=list[dict])
@limiter.limit("30/minute")
def get_moderation_audit_log(
    request: Request,
    branch: str,
    master_key: str = Depends(get_branch_master_key),
    session: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
):
    """
    Get the moderation audit log for a branch.
    
    Requires the X-Branch-Master-Key header.
    Returns all moderation actions performed on this branch.
    """
    verify_branch_moderator_secure(session, branch, master_key)
    
    logs = session.execute(
        select(ModerationLog)
        .where(ModerationLog.branch == branch)
        .order_by(ModerationLog.timestamp.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    ).scalars().all()
    
    return [
        {
            "id": log.id,
            "action": log.action,
            "target_id": log.target_id,
            "target_type": log.target_type,
            "details": log.details,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address,
        }
        for log in logs
    ]
