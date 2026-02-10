#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Stdio Server

This server implements the MCP protocol over stdio transport,
exposing all tools from the OpenX MCP module.

Usage:
    uv run python mcp_server.py

Authentication:
    Tools that require authentication expect a 'secret_key' argument.
    This is the user's secret key for the OpenX platform.
"""
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)

from src.core.db.session import SessionLocal
from src.core.db.tables.secretkey import SecretKey
from src.core.security import verify_key
from src.api.mcp.main import (
    TOOLS as MCP_TOOLS,
    execute_tool,
    AuthRequiredError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


# Create the MCP server instance
server = Server(
    name="OpenX",
    version="1.0.0",
    instructions=(
        "OpenX is a Reddit-like social platform. Use tools to interact with posts, "
        "branches (communities), and comments. Authentication via 'secret_key' parameter "
        "is required for write operations."
    ),
)


def convert_tool_to_mcp(tool) -> Tool:
    """Convert a tool from src.api.mcp.models.Tool to mcp.types.Tool."""
    # inputSchema is a Pydantic model class, get its JSON schema
    schema = tool.inputSchema.model_json_schema()
    return Tool(
        name=tool.name,
        description=tool.description,
        inputSchema=schema,
    )


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return all available tools from the MCP module."""
    return [convert_tool_to_mcp(tool) for tool in MCP_TOOLS]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> CallToolResult:
    """
    Handle tool execution by delegating to execute_tool from the MCP module.

    For tools requiring authentication, the 'secret_key' argument is used
    to authenticate the user.
    """
    arguments = arguments or {}

    # Extract secret_key for authentication if provided
    secret_key = arguments.pop("secret_key", None)
    current_user = None

    # Create a database session
    session = SessionLocal()

    try:
        # Authenticate user if secret_key is provided
        if secret_key:
            sk_id = secret_key[:16] if len(secret_key) >= 16 else secret_key
            from sqlalchemy import select
            sk_object = session.execute(
                select(SecretKey).where(SecretKey.sk_id == sk_id)
            ).scalar()
            if sk_object and verify_key(secret_key, sk_object.sk_hash):
                current_user = sk_object

        # Execute the tool
        result = execute_tool(name, arguments, current_user, session)

        # Convert the result content to MCP TextContent format
        content_blocks = []
        for content_item in result.content:
            if content_item.get("type") == "text":
                content_blocks.append(
                    TextContent(type="text", text=content_item.get("text", ""))
                )
            else:
                # Handle other content types by converting to JSON string
                content_blocks.append(
                    TextContent(type="text", text=json.dumps(content_item))
                )

        return CallToolResult(
            content=content_blocks,
            isError=result.isError,
        )

    except AuthRequiredError as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Authentication required: {str(e)}")],
            isError=True,
        )
    except ForbiddenError as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Forbidden: {str(e)}")],
            isError=True,
        )
    except NotFoundError as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Not found: {str(e)}")],
            isError=True,
        )
    except ValidationError as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Validation error: {str(e)}")],
            isError=True,
        )
    except Exception as e:
        # Handle errors by returning an error result
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            isError=True,
        )
    finally:
        session.close()


async def main():
    """Run the MCP stdio server."""
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
