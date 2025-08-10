"""
MCP server definition for the Dev Tools MCP.
"""

import logging
from typing import Any, List, Optional

from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware

from mcp.server.fastmcp import Context, FastMCP

from dev_tools_mcp.prompts import get_prompts
from dev_tools_mcp.tools.base import Tool
from dev_tools_mcp.utils.config import ServiceConfig
from dev_tools_mcp.utils.dependencies import (
    get_base_config,
    get_bash_tool_provider,
    get_file_editor_tool_provider,
    get_json_editor_tool_provider,
    get_code_search_tool_provider,
    get_git_tool_provider,
    get_sequential_thinking_tool_provider,
    get_task_done_tool_provider,
)


# Get a module-level logger
logger = logging.getLogger(__name__)


class CustomFastMCP(FastMCP):
    """Custom FastMCP server with CORS middleware."""

    def _add_cors_middleware(self, app: Starlette) -> Starlette:
        """A helper to add CORS middleware to a Starlette app."""
        app.user_middleware.insert(
            0,
            Middleware(
                CORSMiddleware,
                allow_origin_regex=".*",  # Allow any origin
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        )
        app.middleware_stack = app.build_middleware_stack()
        return app

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        """Overrides the default sse_app to inject CORS middleware."""
        app = super().sse_app(mount_path)
        return self._add_cors_middleware(app)

    def streamable_http_app(self) -> Starlette:
        """Overrides the default streamable_http_app to inject CORS middleware."""
        app = super().streamable_http_app()
        return self._add_cors_middleware(app)


def build_server(config: ServiceConfig) -> CustomFastMCP:
    """Build and configure the FastMCP server instance.

    Args:
        config: The server's service configuration.

    Returns:
        A configured CustomFastMCP instance.
    """
    logger.info(
        "Initializing FastMCP server",
        extra={"host": config.MCP_HOST, "port": config.MCP_PORT},
    )
    return CustomFastMCP(
        "dev-tools-mcp",
        host=config.MCP_HOST,
        port=config.MCP_PORT,
    )

# Get the base configuration for server initialization.
# This is also imported by main.py to run the server.
server_config = get_base_config()
mcp_app = build_server(server_config)


# --- Prompt Handlers ---
@mcp_app.prompt(title="Agent System Prompt for Dev Tools")
def get_system_prompt() -> str:
    """Provides the main system prompt for the agent."""
    prompts = get_prompts()
    return prompts["agent-system-prompt"]

# --- Tool Definitions ---

@mcp_app.tool()
async def bash(
    context: Context,
    command: str,
    restart: bool = False,
) -> dict[str, Any]:
    """
    Executes a shell command in a persistent session.

    Args:
        command: The command to execute.
        restart: Whether to restart the bash session before executing.

    Returns:
        A dictionary containing the command's stdout, stderr, and exit code.
    """
    logger.info(f"Executing bash command: {command}")
    try:
        bash_tool = get_bash_tool_provider()
        # The `execute` method of the tool expects a single dictionary of arguments.
        args = {"command": command, "restart": restart}
        result = await bash_tool.execute(args)
        return {
            "stdout": result.output,
            "stderr": result.error,
            "exit_code": result.error_code,
        }
    except Exception as e:
        logger.error(f"Error executing bash command: {e}", exc_info=True)
        # It's better to return a structured error than to let the exception bubble up
        return {"stdout": "", "stderr": str(e), "exit_code": 1}


@mcp_app.tool(name="file_editor")
async def file_editor_tool(
    context: Context,
    command: str,
    path: str,
    file_text: Optional[str] = None,
    old_str: Optional[str] = None,
    new_str: Optional[str] = None,
    insert_line: Optional[int] = None,
    view_range: Optional[List[int]] = None,
) -> dict[str, Any]:
    """
    A powerful tool for file manipulation (view, create, str_replace, insert).

    Args:
        command: The type of operation. Can be 'view', 'create', 'str_replace', or 'insert'.
        path: The absolute path to the file or directory.
        file_text: The content for a 'create' operation.
        old_str: The string to search for in a 'str_replace' operation. Must be unique.
        new_str: The replacement string for 'str_replace' or the content for 'insert'.
        insert_line: The line number for an 'insert' operation (inserts AFTER this line).
        view_range: The line range to view (e.g., [10, 25]).

    Returns:
        A dictionary containing the result of the operation.
    """
    logger.info(f"Executing file_editor command '{command}' on path '{path}'")
    try:
        editor_tool = get_file_editor_tool_provider()
        args = {
            "command": command,
            "path": path,
            "file_text": file_text,
            "old_str": old_str,
            "new_str": new_str,
            "insert_line": insert_line,
            "view_range": view_range,
        }
        # Filter out None values so we don't pass them to the tool
        args = {k: v for k, v in args.items() if v is not None}

        result = await editor_tool.execute(args)
        if result.error:
            return {"status": "error", "error": result.error, "exit_code": result.error_code}
        return {"status": "success", "result": result.output, "exit_code": result.error_code}

    except Exception as e:
        logger.error(f"Error executing file_editor command: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "exit_code": 1}


@mcp_app.tool()
async def json_editor(
    context: Context,
    operation: str,
    file_path: str,
    json_path: Optional[str] = None,
    value: Optional[Any] = None,
    pretty_print: bool = True,
) -> dict[str, Any]:
    """
    Tool for editing JSON files with JSONPath expressions.

    Args:
        operation: The operation to perform. Can be 'view', 'set', 'add', or 'remove'.
        file_path: The absolute path to the JSON file.
        json_path: JSONPath expression to specify the target location.
        value: The JSON-serializable value to set or add.
        pretty_print: Whether to format the JSON output with indentation.

    Returns:
        A dictionary containing the result of the operation.
    """
    logger.info(f"Executing json_editor operation '{operation}' on file '{file_path}'")
    try:
        json_editor_tool = get_json_editor_tool_provider()
        args = {
            "operation": operation,
            "file_path": file_path,
            "json_path": json_path,
            "value": value,
            "pretty_print": pretty_print,
        }
        # Filter out None values for optional tool arguments
        args = {k: v for k, v in args.items() if v is not None}

        result = await json_editor_tool.execute(args)
        if result.error:
            return {"status": "error", "error": result.error, "exit_code": result.error_code}
        return {"status": "success", "result": result.output, "exit_code": result.error_code}

    except Exception as e:
        logger.error(f"Error executing json_editor operation: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "exit_code": 1}


# --- CKG Tool (Feature Flagged) ---
if server_config.FEATURE_CKG_ENABLED:
    logger.info("CKG feature is enabled. Registering 'code_search' tool.")

    @mcp_app.tool(name="code_search")
    async def code_search_tool(
        context: Context,
        command: str,
        path: str,
        identifier: str,
        print_body: bool = True,
    ) -> dict[str, Any]:
        """
        Query the code knowledge graph (CKG) of a codebase for specific symbols.
        The CKG is indexed automatically and kept in sync with the filesystem, providing reliable, up-to-date results.

        Args:
            command: The type of search. Can be 'search_function', 'search_class', or 'search_class_method'.
            path: The path to the codebase to be searched.
            identifier: The name of the function, class, or method to search for.
            print_body: Whether to print the body of the found symbol. Defaults to true.

        Returns:
            A dictionary containing the search results.
        """
        logger.info(f"Executing code_search command '{command}' on path '{path}'")
        try:
            ckg_tool = get_code_search_tool_provider()
            args = {
                "command": command,
                "path": path,
                "identifier": identifier,
                "print_body": print_body,
            }
            result = await ckg_tool.execute(args)
            if result.error:
                return {"status": "error", "error": result.error, "exit_code": result.error_code}
            return {"status": "success", "result": result.output, "exit_code": result.error_code}

        except Exception as e:
            logger.error(f"Error executing code_search command: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "exit_code": 1}
else:
    logger.warning("CKG feature is disabled. The 'code_search' tool will not be available.")


@mcp_app.tool(name="git")
async def git_tool(
    context: Context,
    command: str,
    path: str,
    base_commit: Optional[str] = None,
    message: Optional[str] = None,
    add_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    A comprehensive tool for interacting with a Git repository.
    This tool is self-contained and operates on the specified repository path without changing the global working directory.

    Args:
        command: The git command to execute. Must be one of: 'status', 'diff', 'add', 'commit', 'restore'.
        path: The absolute path to the Git repository.
        base_commit: For the 'diff' command. The commit hash to diff against. If not provided, shows current uncommitted changes.
        message: For the 'commit' command. The commit message. This is a required argument for 'commit'.
        add_path: For 'add' and 'restore' commands. The path of files/directories to add or restore. Defaults to '.' (all files in the repo).

    Returns:
        A dictionary containing the result of the git operation.
    """
    logger.info(f"Executing git command '{command}' on path '{path}'")
    try:
        tool = get_git_tool_provider()
        args = {
            "command": command,
            "path": path,
            "base_commit": base_commit,
            "message": message,
            "add_path": add_path,
        }
        args = {k: v for k, v in args.items() if v is not None}

        result = await tool.execute(args)
        if result.error:
            return {"status": "error", "error": result.error, "exit_code": result.error_code}
        return {"status": "success", "result": result.output, "exit_code": result.error_code}

    except Exception as e:
        logger.error(f"Error executing git command: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "exit_code": 1}


@mcp_app.tool()
async def sequential_thinking(
    context: Context,
    thought: str,
    next_thought_needed: bool,
    thought_number: int,
    total_thoughts: int,
    is_revision: Optional[bool] = None,
    revises_thought: Optional[int] = None,
    branch_from_thought: Optional[int] = None,
    branch_id: Optional[str] = None,
    needs_more_thoughts: Optional[bool] = None,
) -> dict[str, Any]:
    """
    A tool for dynamic and reflective problem-solving through thoughts.

    Args:
        thought: Your current thinking step.
        next_thought_needed: Whether another thought step is needed.
        thought_number: Current thought number (min: 1).
        total_thoughts: Estimated total thoughts needed (min: 1).
        is_revision: Whether this revises previous thinking.
        revises_thought: Which thought is being reconsidered (min: 1).
        branch_from_thought: Branching point thought number (min: 1).
        branch_id: Branch identifier.
        needs_more_thoughts: If more thoughts are needed.

    Returns:
        A dictionary containing the status of the thinking process.
    """
    logger.info(f"Executing sequential_thinking step {thought_number}/{total_thoughts}")
    try:
        thinking_tool = get_sequential_thinking_tool_provider()
        args = {
            "thought": thought,
            "next_thought_needed": next_thought_needed,
            "thought_number": thought_number,
            "total_thoughts": total_thoughts,
            "is_revision": is_revision,
            "revises_thought": revises_thought,
            "branch_from_thought": branch_from_thought,
            "branch_id": branch_id,
            "needs_more_thoughts": needs_more_thoughts,
        }
        args = {k: v for k, v in args.items() if v is not None}

        result = await thinking_tool.execute(args)
        if result.error:
            return {"status": "error", "error": result.error, "exit_code": result.error_code}
        return {"status": "success", "result": result.output, "exit_code": result.error_code}

    except Exception as e:
        logger.error(f"Error executing sequential_thinking: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "exit_code": 1}


@mcp_app.tool()
async def task_done(
    context: Context,
) -> dict[str, Any]:
    """
    Reports the completion of the task.

    Returns:
        A dictionary with a confirmation message.
    """
    logger.info("Executing task_done.")
    try:
        task_done_tool = get_task_done_tool_provider()
        result = await task_done_tool.execute({})
        if result.error:
            return {"status": "error", "error": result.error, "exit_code": result.error_code}
        return {"status": "success", "result": result.output, "exit_code": result.error_code}

    except Exception as e:
        logger.error(f"Error executing task_done: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "exit_code": 1}
