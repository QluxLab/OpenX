from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import bleach


MAX_PAGE_LIMIT = 1000
DEFAULT_PAGE_LIMIT = 100


class PaginationParams(BaseModel):
    """Pagination parameters with enforced limits."""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT, description="Maximum items to return")


class BranchCreate(BaseModel):
    """Request schema for creating a branch"""
    name: str = Field(..., min_length=3, max_length=256, pattern=r'^[a-zA-Z0-9_-]+$')
    description: str | None = Field(None, max_length=4096)
    
    @field_validator('description')
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        """Sanitize description to prevent XSS"""
        if v:
            return bleach.clean(v, tags=[], strip=True)
        return v


class BranchUpdate(BaseModel):
    """Request schema for updating branch settings (moderation)"""
    description: str | None = Field(None, max_length=4096)
    
    @field_validator('description')
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        """Sanitize description to prevent XSS"""
        if v:
            return bleach.clean(v, tags=[], strip=True)
        return v


class BranchResponse(BaseModel):
    """Response schema for branch info (public)"""
    name: str
    description: str | None = None
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class BranchCreateResponse(BaseModel):
    """Response schema when creating a branch - includes master key (only shown once!)"""
    name: str
    description: str | None = None
    master_key: str  # Only returned on creation!
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class MasterKeyRotateResponse(BaseModel):
    """Response schema for master key rotation"""
    name: str
    master_key: str  # New master key (only shown once!)
    message: str = "Master key rotated successfully. Store the new key securely."


class BranchDeleteConfirm(BaseModel):
    """Confirmation schema for branch deletion to prevent accidental deletions."""
    branch_name: str = Field(..., description="Must match the branch being deleted")
    confirmation: str = Field(..., pattern=r'^DELETE$', description="Must be 'DELETE'")