"""
Moderation audit log table for tracking all moderation actions.
"""
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime

from src.core.db.tables.base import Base


class ModerationLog(Base):
    """
    Audit log for all moderation actions.
    
    This table records all moderation actions for accountability,
    forensic capability, and compliance requirements.
    """
    
    __tablename__ = "moderation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch: Mapped[str] = mapped_column(String(256), index=True)
    action: Mapped[str] = mapped_column(String(50))  # "delete_post", "update_settings", "delete_branch", "rotate_key"
    moderator_key_hash: Mapped[str] = mapped_column(String(256))  # Hash of the master key used (for accountability)
    target_id: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Post ID, etc.
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "post", "branch", "settings"
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON details of the action
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


def log_moderation_action(
    session,
    branch: str,
    action: str,
    moderator_key_hash: str,
    target_id: str | None = None,
    target_type: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ModerationLog:
    """
    Log a moderation action to the audit trail.
    
    Args:
        session: Database session
        branch: Branch name where action occurred
        action: Type of action (delete_post, update_settings, delete_branch, rotate_key)
        moderator_key_hash: Hash of the master key used for the action
        target_id: ID of the target (post_id, etc.)
        target_type: Type of target (post, branch, settings)
        details: JSON string with additional details
        ip_address: IP address of the requester
        user_agent: User agent of the requester
        
    Returns:
        The created ModerationLog entry
    """
    log_entry = ModerationLog(
        branch=branch,
        action=action,
        moderator_key_hash=moderator_key_hash,
        target_id=target_id,
        target_type=target_type,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(log_entry)
    return log_entry