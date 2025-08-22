from pathlib import Path

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import ToolError


def resolve_path(
    state: FileSystemState, path_str: str, must_be_relative: bool = False
) -> Path:
    """
    Resolves a user-provided path against the session state, ensuring it's within the sandbox.

    Args:
        state: The current FileSystemState for the session.
        path_str: The path string provided by the user.
        must_be_relative: If True, the path is not allowed to be absolute.

    Returns:
        A resolved, validated Path object.

    Raises:
        ToolError: If the path is invalid or outside the sandbox.
        PermissionError: If the path escapes the sandbox root.
    """
    path = Path(path_str).expanduser()

    if must_be_relative and path.is_absolute():
        raise ToolError(f"Path '{path_str}' must be relative in the 'edit' phase.")

    target_path = state.cwd / path if not path.is_absolute() else path

    try:
        resolved_path = target_path.resolve()
        if state.phase == "edit" and not resolved_path.is_relative_to(state.root.resolve()):
            raise PermissionError("Path is outside the sandbox")
    except FileNotFoundError:
        # Allow creating new files in existing directories
        if not target_path.parent.exists():
            raise
        resolved_path = target_path
        if state.phase == "edit" and not resolved_path.is_relative_to(state.root.resolve()):
            raise PermissionError("Path is outside the sandbox")

    return resolved_path
