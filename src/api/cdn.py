import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter(prefix="/cdn")

# Configuration - should match media upload settings
CDN_STORAGE_PATH = os.getenv("OPENX_CDN_PATH", "./.data/uploads")


@router.get("/{filename}")
def serve_media(filename: str):
    """
    Serve uploaded media files.
    Public endpoint - no authentication required.
    """
    # Security: prevent path traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    file_path = Path(CDN_STORAGE_PATH) / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found",
        )

    return FileResponse(
        path=file_path,
        headers={
            "Cache-Control": "public, max-age=31536000",  # 1 year cache
        }
    )
