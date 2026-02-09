import os
import uuid
import filetype
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.db.tables.media import Media
from src.core.db.tables.secretkey import SecretKey
from src.core.db.session import get_db, get_current_user
from src.core.logger import get_logger
from src.api.v0.media.models import (
    MediaUploadResponse,
    MediaListResponse,
    MediaDeleteResponse,
    ALLOWED_CONTENT_TYPES,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
)

# Initialize logger
logger = get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/media")

# Configuration - can be overridden via environment variables
CDN_BASE_URL = os.getenv("OPENX_CDN_URL", "http://localhost:8000/cdn")
CDN_STORAGE_PATH = os.getenv("OPENX_CDN_PATH", "./.data/uploads")

# Chunk size for streaming uploads (1MB)
CHUNK_SIZE = 1024 * 1024


def get_media_type(content_type: str) -> str | None:
    """Determine media type from content type"""
    if content_type in ALLOWED_IMAGE_TYPES:
        return "image"
    elif content_type in ALLOWED_VIDEO_TYPES:
        return "video"
    return None


def get_max_size(media_type: str) -> int:
    """Get max file size for media type"""
    return MAX_IMAGE_SIZE if media_type == "image" else MAX_VIDEO_SIZE


def generate_media_id() -> str:
    """Generate a unique media ID"""
    return uuid.uuid4().hex


def ensure_upload_dir(storage_path: str) -> Path:
    """Ensure upload directory exists"""
    upload_dir = Path(storage_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def validate_file_by_magic_bytes(file_path: Path) -> str | None:
    """
    Validate file type using magic bytes.
    Returns the detected MIME type or None if invalid.
    """
    try:
        kind = filetype.guess(file_path)
        if kind is None:
            return None
        return kind.mime
    except Exception:
        return None


@router.post("/upload", response_model=MediaUploadResponse)
@limiter.limit("20/minute")
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Upload media file for posts.

    Accepts images (JPEG, PNG, GIF, WebP) up to 10MB and videos (MP4, WebM, OGG) up to 100MB.
    Rate limited to 20 uploads per minute per IP.
    Requires authentication via X-Secret-Key header.

    Files are streamed to disk to avoid memory issues and validated using magic bytes.
    """
    # Validate content type header (preliminary check)
    if not file.content_type or file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type. Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    media_type = get_media_type(file.content_type)
    max_size = get_max_size(media_type)

    # Generate unique ID and storage path
    media_id = generate_media_id()

    # Preserve original file extension
    original_filename = file.filename or "upload"
    file_ext = Path(original_filename).suffix or ""
    stored_filename = f"{media_id}{file_ext}"

    # Ensure upload directory exists
    upload_dir = ensure_upload_dir(CDN_STORAGE_PATH)
    storage_path = upload_dir / stored_filename

    # Stream file to disk with size checking
    total_size = 0
    try:
        with open(storage_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                total_size += len(chunk)

                # Check size limit during streaming
                if total_size > max_size:
                    # Clean up partial file
                    storage_path.unlink(missing_ok=True)
                    max_size_mb = max_size // (1024 * 1024)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size for {media_type}s is {max_size_mb}MB",
                    )

                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Clean up on any error
        storage_path.unlink(missing_ok=True)
        logger.error(f"Error streaming file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file",
        )

    # Check if file is empty
    if total_size == 0:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file not allowed",
        )

    # Validate file type using magic bytes (not just Content-Type header)
    detected_mime = validate_file_by_magic_bytes(storage_path)
    if not detected_mime or detected_mime not in ALLOWED_CONTENT_TYPES:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match allowed types or could not be validated",
        )

    # Update media type based on actual file content
    actual_media_type = get_media_type(detected_mime)

    # Build CDN URL
    cdn_url = f"{CDN_BASE_URL}/{stored_filename}"

    # Create database record
    media_record = Media(
        id=media_id,
        username=current_user.username,
        url=cdn_url,
        media_type=actual_media_type,
        filename=original_filename,
        size_bytes=total_size,
        content_type=detected_mime,
        storage_path=str(storage_path),
    )

    session.add(media_record)
    session.commit()
    session.refresh(media_record)

    logger.info(f"Media uploaded: {media_id} by user {current_user.username}")

    return MediaUploadResponse(
        id=media_id,
        url=cdn_url,
        media_type=actual_media_type,
        filename=original_filename,
        size_bytes=total_size,
        content_type=detected_mime,
        created_at=media_record.created_at,
    )


@router.get("/list", response_model=list[MediaListResponse])
def list_user_media(
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    List all media uploaded by the authenticated user.
    Requires authentication via X-Secret-Key header.
    """
    media_list = session.execute(
        select(Media)
        .where(Media.username == current_user.username)
        .order_by(Media.created_at.desc())
    ).scalars().all()

    return [MediaListResponse.model_validate(m) for m in media_list]


@router.delete("/{media_id}", response_model=MediaDeleteResponse)
def delete_media(
    media_id: str,
    current_user: SecretKey = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """
    Delete a media file by ID.
    Only the owner can delete their media.
    Requires authentication via X-Secret-Key header.
    """
    media_record = session.execute(
        select(Media).where(Media.id == media_id)
    ).scalar()

    if not media_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found",
        )

    # Check ownership
    if media_record.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own media",
        )

    # Delete file from disk
    try:
        storage_path = Path(media_record.storage_path)
        if storage_path.exists():
            storage_path.unlink()
    except Exception:
        pass  # Continue even if file deletion fails

    # Delete database record
    session.delete(media_record)
    session.commit()

    logger.info(f"Media deleted: {media_id} by user {current_user.username}")

    return MediaDeleteResponse(id=media_id)


@router.get("/{media_id}", response_model=MediaListResponse)
def get_media_info(
    media_id: str,
    session: Session = Depends(get_db),
):
    """
    Get information about a specific media file.
    Public endpoint - no authentication required.
    """
    media_record = session.execute(
        select(Media).where(Media.id == media_id)
    ).scalar()

    if not media_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found",
        )

    return MediaListResponse.model_validate(media_record)
