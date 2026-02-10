"""
MCP tools implementation for OpenX.

This module wraps the existing API functionality to expose them as MCP tools
that can be called via the stdio MCP server.
"""
import json
from typing import Any
from dataclasses import dataclass, field
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.tables.secretkey import SecretKey
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.branch import Branch
from src.core.db.tables.comment import Comment
from src.core.security import verify_key
from src.api.v0.user.models import get_post_model, get_response_schema


# Error classes
class AuthRequiredError(Exception):
    """Raised when authentication is required but not provided."""
    pass


class ForbiddenError(Exception):
    """Raised when user doesn't have permission for the action."""
    pass


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


@dataclass
class ToolResult:
    """Result from tool execution."""
    content: list[dict]
    isError: bool = False


class ToolInputSchema(BaseModel):
    """Base class for tool input schemas."""
    pass


@dataclass
class Tool:
    """Represents an MCP tool definition."""
    name: str
    description: str
    inputSchema: ToolInputSchema


# Tool input schemas
class GetCurrentUserInput(ToolInputSchema):
    pass


class VerifyAuthInput(ToolInputSchema):
    secret_key: str


class ListPostsInput(ToolInputSchema):
    branch: str | None = None
    username: str | None = None
    limit: int = 20
    offset: int = 0


class GetPostInput(ToolInputSchema):
    post_id: int


class CreatePostInput(ToolInputSchema):
    title: str
    content: str
    post_type: str = "text"
    to_branch: str | None = None


class DeletePostInput(ToolInputSchema):
    post_id: int


class SearchInput(ToolInputSchema):
    query: str
    limit: int = 20


class ListBranchesInput(ToolInputSchema):
    limit: int = 50
    offset: int = 0


class GetBranchInput(ToolInputSchema):
    branch_name: str


class CreateBranchInput(ToolInputSchema):
    name: str
    description: str = ""


class GetCommentsInput(ToolInputSchema):
    post_id: int


class CreateCommentInput(ToolInputSchema):
    post_id: int
    content: str
    parent_id: int | None = None


class DeleteCommentInput(ToolInputSchema):
    comment_id: int


# Tool definitions
TOOLS = [
    Tool(
        name="get_current_user",
        description="Get information about the currently authenticated user. Requires authentication.",
        inputSchema=GetCurrentUserInput,
    ),
    Tool(
        name="verify_auth",
        description="Verify if a secret key is valid and return the associated username.",
        inputSchema=VerifyAuthInput,
    ),
    Tool(
        name="list_posts",
        description="List posts from OpenX. Can filter by branch or username.",
        inputSchema=ListPostsInput,
    ),
    Tool(
        name="get_post",
        description="Get a specific post by its ID.",
        inputSchema=GetPostInput,
    ),
    Tool(
        name="create_post",
        description="Create a new post. Requires authentication.",
        inputSchema=CreatePostInput,
    ),
    Tool(
        name="delete_post",
        description="Delete a post by ID. Requires authentication (must be the author).",
        inputSchema=DeletePostInput,
    ),
    Tool(
        name="search",
        description="Search posts by title or content.",
        inputSchema=SearchInput,
    ),
    Tool(
        name="list_branches",
        description="List all available branches (communities).",
        inputSchema=ListBranchesInput,
    ),
    Tool(
        name="get_branch",
        description="Get information about a specific branch.",
        inputSchema=GetBranchInput,
    ),
    Tool(
        name="create_branch",
        description="Create a new branch. Requires authentication.",
        inputSchema=CreateBranchInput,
    ),
    Tool(
        name="get_comments",
        description="Get all comments for a post.",
        inputSchema=GetCommentsInput,
    ),
    Tool(
        name="create_comment",
        description="Add a comment to a post. Requires authentication.",
        inputSchema=CreateCommentInput,
    ),
    Tool(
        name="delete_comment",
        description="Delete a comment. Requires authentication (must be the author).",
        inputSchema=DeleteCommentInput,
    ),
]


def _build_comment_tree(comments: list[Comment]) -> list[dict]:
    """Build nested comment tree from flat list."""
    comment_map = {}
    root_comments = []

    for comment in comments:
        comment_map[comment.id] = {
            "id": comment.id,
            "post_id": comment.post_id,
            "username": comment.username,
            "content": comment.content,
            "parent_id": comment.parent_id,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "replies": []
        }

    for comment in comments:
        node = comment_map[comment.id]
        if comment.parent_id is None:
            root_comments.append(node)
        elif comment.parent_id in comment_map:
            comment_map[comment.parent_id]["replies"].append(node)

    return root_comments


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    current_user: SecretKey | None,
    session: Session,
) -> ToolResult:
    """
    Execute an MCP tool by name with the given arguments.

    Args:
        name: The tool name to execute
        arguments: The tool arguments
        current_user: The authenticated user (if any)
        session: Database session

    Returns:
        ToolResult with content blocks and error status
    """
    try:
        if name == "get_current_user":
            return _tool_get_current_user(current_user)

        elif name == "verify_auth":
            return _tool_verify_auth(arguments, session)

        elif name == "list_posts":
            return _tool_list_posts(arguments, session)

        elif name == "get_post":
            return _tool_get_post(arguments, session)

        elif name == "create_post":
            return _tool_create_post(arguments, current_user, session)

        elif name == "delete_post":
            return _tool_delete_post(arguments, current_user, session)

        elif name == "search":
            return _tool_search(arguments, session)

        elif name == "list_branches":
            return _tool_list_branches(arguments, session)

        elif name == "get_branch":
            return _tool_get_branch(arguments, session)

        elif name == "create_branch":
            return _tool_create_branch(arguments, current_user, session)

        elif name == "get_comments":
            return _tool_get_comments(arguments, session)

        elif name == "create_comment":
            return _tool_create_comment(arguments, current_user, session)

        elif name == "delete_comment":
            return _tool_delete_comment(arguments, current_user, session)

        else:
            return ToolResult(
                content=[{"type": "text", "text": f"Unknown tool: {name}"}],
                isError=True,
            )

    except AuthRequiredError as e:
        return ToolResult(
            content=[{"type": "text", "text": f"Authentication required: {str(e)}"}],
            isError=True,
        )
    except ForbiddenError as e:
        return ToolResult(
            content=[{"type": "text", "text": f"Forbidden: {str(e)}"}],
            isError=True,
        )
    except NotFoundError as e:
        return ToolResult(
            content=[{"type": "text", "text": f"Not found: {str(e)}"}],
            isError=True,
        )
    except ValidationError as e:
        return ToolResult(
            content=[{"type": "text", "text": f"Validation error: {str(e)}"}],
            isError=True,
        )
    except Exception as e:
        return ToolResult(
            content=[{"type": "text", "text": f"Error: {str(e)}"}],
            isError=True,
        )


def _tool_get_current_user(current_user: SecretKey | None) -> ToolResult:
    """Get current user info."""
    if not current_user:
        raise AuthRequiredError("Authentication required")

    return ToolResult(
        content=[{
            "type": "text",
            "text": json.dumps({
                "username": current_user.username,
                "sk_id": current_user.sk_id,
            })
        }]
    )


def _tool_verify_auth(arguments: dict, session: Session) -> ToolResult:
    """Verify a secret key."""
    secret_key = arguments.get("secret_key")
    if not secret_key:
        raise ValidationError("secret_key is required")

    sk_id = secret_key[:16] if len(secret_key) >= 16 else secret_key
    sk_object = session.execute(
        select(SecretKey).where(SecretKey.sk_id == sk_id)
    ).scalar()

    if sk_object and verify_key(secret_key, sk_object.sk_hash):
        return ToolResult(
            content=[{
                "type": "text",
                "text": json.dumps({
                    "valid": True,
                    "username": sk_object.username
                })
            }]
        )

    return ToolResult(
        content=[{"type": "text", "text": json.dumps({"valid": False})}]
    )


def _tool_list_posts(arguments: dict, session: Session) -> ToolResult:
    """List posts with optional filters."""
    branch = arguments.get("branch")
    username = arguments.get("username")
    limit = min(arguments.get("limit", 20), 100)
    offset = arguments.get("offset", 0)

    query = select(UserPost)

    if branch:
        query = query.where(UserPost.branch == branch)
    if username:
        query = query.where(UserPost.username == username)

    posts = session.execute(
        query.offset(offset).limit(limit)
    ).scalars().all()

    results = [get_response_schema(post).model_dump() for post in posts]
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(results, default=str)}]
    )


def _tool_get_post(arguments: dict, session: Session) -> ToolResult:
    """Get a post by ID."""
    post_id = arguments.get("post_id")
    if not post_id:
        raise ValidationError("post_id is required")

    post = session.execute(
        select(UserPost).where(UserPost.id == post_id)
    ).scalar()

    if not post:
        raise NotFoundError(f"Post {post_id} not found")

    result = get_response_schema(post).model_dump()
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(result, default=str)}]
    )


def _tool_create_post(arguments: dict, current_user: SecretKey | None, session: Session) -> ToolResult:
    """Create a new post."""
    if not current_user:
        raise AuthRequiredError("Authentication required")

    title = arguments.get("title")
    content = arguments.get("content")
    post_type = arguments.get("post_type", "text")
    to_branch = arguments.get("to_branch")

    if not title:
        raise ValidationError("title is required")

    model_class = get_post_model(post_type)
    if not model_class:
        raise ValidationError(f"Unknown post type: {post_type}")

    if to_branch:
        branch_exists = session.execute(
            select(Branch).where(Branch.name == to_branch, Branch.deleted_at.is_(None))
        ).scalar()
        if not branch_exists:
            raise NotFoundError(f"Branch '{to_branch}' not found")

    post = model_class(
        title=title,
        content=content,
        username=current_user.username,
        branch=to_branch,
    )

    session.add(post)
    session.commit()
    session.refresh(post)

    result = get_response_schema(post).model_dump()
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(result, default=str)}]
    )


def _tool_delete_post(arguments: dict, current_user: SecretKey | None, session: Session) -> ToolResult:
    """Delete a post."""
    if not current_user:
        raise AuthRequiredError("Authentication required")

    post_id = arguments.get("post_id")
    if not post_id:
        raise ValidationError("post_id is required")

    post = session.execute(
        select(UserPost).where(UserPost.id == post_id)
    ).scalar()

    if not post:
        raise NotFoundError(f"Post {post_id} not found")

    if post.username != current_user.username:
        raise ForbiddenError("Not authorized to delete this post")

    session.delete(post)
    session.commit()

    return ToolResult(
        content=[{"type": "text", "text": json.dumps({"success": True, "message": f"Post {post_id} deleted"})}]
    )


def _tool_search(arguments: dict, session: Session) -> ToolResult:
    """Search posts."""
    query_str = arguments.get("query")
    limit = min(arguments.get("limit", 20), 100)

    if not query_str:
        raise ValidationError("query is required")

    posts = session.execute(
        select(UserPost)
        .where(
            (UserPost.title.ilike(f"%{query_str}%")) |
            (UserPost.content.ilike(f"%{query_str}%"))
        )
        .limit(limit)
    ).scalars().all()

    results = [get_response_schema(post).model_dump() for post in posts]
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(results, default=str)}]
    )


def _tool_list_branches(arguments: dict, session: Session) -> ToolResult:
    """List all branches."""
    limit = min(arguments.get("limit", 50), 100)
    offset = arguments.get("offset", 0)

    branches = session.execute(
        select(Branch)
        .where(Branch.deleted_at.is_(None))
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    results = [{
        "name": b.name,
        "description": b.description,
        "created_by": b.created_by,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    } for b in branches]

    return ToolResult(
        content=[{"type": "text", "text": json.dumps(results)}]
    )


def _tool_get_branch(arguments: dict, session: Session) -> ToolResult:
    """Get branch info."""
    branch_name = arguments.get("branch_name")
    if not branch_name:
        raise ValidationError("branch_name is required")

    branch = session.execute(
        select(Branch).where(Branch.name == branch_name, Branch.deleted_at.is_(None))
    ).scalar()

    if not branch:
        raise NotFoundError(f"Branch '{branch_name}' not found")

    result = {
        "name": branch.name,
        "description": branch.description,
        "created_by": branch.created_by,
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
    }

    return ToolResult(
        content=[{"type": "text", "text": json.dumps(result)}]
    )


def _tool_create_branch(arguments: dict, current_user: SecretKey | None, session: Session) -> ToolResult:
    """Create a new branch."""
    if not current_user:
        raise AuthRequiredError("Authentication required")

    from src.core.security import new_branch_master_key, hash_master_key

    name = arguments.get("name")
    description = arguments.get("description", "")

    if not name:
        raise ValidationError("name is required")

    existing = session.execute(
        select(Branch).where(Branch.name == name)
    ).scalar()

    if existing:
        raise ValidationError(f"Branch '{name}' already exists")

    master_key = new_branch_master_key()
    branch = Branch(
        name=name,
        description=description,
        master_key=hash_master_key(master_key),
        created_by=current_user.username,
    )

    session.add(branch)
    session.commit()
    session.refresh(branch)

    result = {
        "name": branch.name,
        "description": branch.description,
        "master_key": master_key,  # Only shown once!
        "created_by": branch.created_by,
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
    }

    return ToolResult(
        content=[{"type": "text", "text": json.dumps(result)}]
    )


def _tool_get_comments(arguments: dict, session: Session) -> ToolResult:
    """Get comments for a post."""
    post_id = arguments.get("post_id")
    if not post_id:
        raise ValidationError("post_id is required")

    post = session.execute(
        select(UserPost).where(UserPost.id == post_id)
    ).scalar()

    if not post:
        raise NotFoundError(f"Post {post_id} not found")

    comments = session.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
    ).scalars().all()

    results = _build_comment_tree(comments)
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(results, default=str)}]
    )


def _tool_create_comment(arguments: dict, current_user: SecretKey | None, session: Session) -> ToolResult:
    """Create a comment."""
    if not current_user:
        raise AuthRequiredError("Authentication required")

    post_id = arguments.get("post_id")
    content = arguments.get("content")
    parent_id = arguments.get("parent_id")

    if not post_id:
        raise ValidationError("post_id is required")
    if not content:
        raise ValidationError("content is required")

    post = session.execute(
        select(UserPost).where(UserPost.id == post_id)
    ).scalar()

    if not post:
        raise NotFoundError(f"Post {post_id} not found")

    if parent_id:
        parent = session.execute(
            select(Comment).where(Comment.id == parent_id)
        ).scalar()
        if not parent:
            raise NotFoundError(f"Parent comment {parent_id} not found")
        if parent.post_id != post_id:
            raise ValidationError("Parent comment must belong to the same post")

    comment = Comment(
        post_id=post_id,
        username=current_user.username,
        content=content,
        parent_id=parent_id,
    )

    session.add(comment)
    session.commit()
    session.refresh(comment)

    result = {
        "id": comment.id,
        "post_id": comment.post_id,
        "username": comment.username,
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }

    return ToolResult(
        content=[{"type": "text", "text": json.dumps(result)}]
    )


def _tool_delete_comment(arguments: dict, current_user: SecretKey | None, session: Session) -> ToolResult:
    """Delete a comment."""
    if not current_user:
        raise AuthRequiredError("Authentication required")

    comment_id = arguments.get("comment_id")
    if not comment_id:
        raise ValidationError("comment_id is required")

    comment = session.execute(
        select(Comment).where(Comment.id == comment_id)
    ).scalar()

    if not comment:
        raise NotFoundError(f"Comment {comment_id} not found")

    if comment.username != current_user.username:
        raise ForbiddenError("Not authorized to delete this comment")

    session.delete(comment)
    session.commit()

    return ToolResult(
        content=[{"type": "text", "text": json.dumps({"success": True, "message": f"Comment {comment_id} deleted"})}]
    )
