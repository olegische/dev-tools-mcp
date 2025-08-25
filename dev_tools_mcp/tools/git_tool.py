import os
import logging
from pathlib import Path
from typing import override, Literal

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import Tool, ToolCallArguments, ToolError, ToolExecResult, ToolParameter
from dev_tools_mcp.tools.run import run
from dev_tools_mcp.utils.path_utils import resolve_path

# Настройка логирования
logger = logging.getLogger(__name__)

GitToolCommands = Literal["status", "diff", "add", "commit", "restore"]

class GitTool(Tool):
    """
    Tool for interacting with Git repositories.
    Supports status, diff, add, commit, and restore operations.
    """

    @override
    def get_name(self) -> str:
        return "git"

    @override
    def get_description(self) -> str:
        return """
        Performs Git operations on a repository.
        - `status`: Shows the working tree status.
        - `diff`: Shows changes between commits, commit and working tree, etc.
        - `add`: Adds file contents to the index.
        - `commit`: Records changes to the repository.
        - `restore`: Restores working tree files to their last committed state (discards uncommitted changes).
        """

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The git command to execute.",
                required=True,
                enum=["status", "diff", "add", "commit", "restore"],
            ),
            ToolParameter(
                name="path",
                type="string",
                description="The path to the Git repository, relative to the CWD.",
                required=True,
            ),
            ToolParameter(
                name="base_commit",
                type="string",
                description="For `diff` command. The commit hash to diff against. If not provided, shows current uncommitted changes.",
                required=False,
            ),
            ToolParameter(
                name="message",
                type="string",
                description="For `commit` command. The commit message.",
                required=False,
            ),
            ToolParameter(
                name="add_path",
                type="string",
                description="For `add` command. The path of files to add. Defaults to '.' (all files).",
                required=False,
            ),
            ToolParameter(
                name="restore_path",
                type="string",
                description="For `restore` command. The path of files to restore. Defaults to '.' (all files).",
                required=False,
            ),
            ToolParameter(
                name="file_path",
                type="string",
                description="For `diff` command. The path of a specific file to diff.",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        state = arguments.get("_fs_state")
        if not isinstance(state, FileSystemState):
            return ToolExecResult(error="FileSystemState not found in arguments.", error_code=-1)

        command = arguments.get("command")
        path_str = arguments.get("path")

        if not command or not isinstance(command, str) or command not in ["status", "diff", "add", "commit", "restore"]:
            return ToolExecResult(error="A valid 'command' is required: status, diff, add, commit, restore.", error_code=1)
        
        if not path_str or not isinstance(path_str, str):
            return ToolExecResult(error="The 'path' parameter is required.", error_code=1)

        try:
            # Check if we have a git repository in state
            if not state.git_root:
                return ToolExecResult(error="No git repository available. Use file_system.lock_cwd() in a directory that contains a git repository.", error_code=1)

            repo_path = resolve_path(state, path_str, must_be_relative=True)
            if not repo_path.is_dir():
                return ToolExecResult(error=f"The provided path is not a directory: {repo_path}", error_code=1)

            # Using `git -C` is crucial for safety in a server environment.
            # It avoids changing the global working directory (`os.chdir`), which is not thread-safe
            # and can lead to race conditions and unpredictable behavior.
            # This approach ensures that all operations are explicitly scoped to the correct repository.
            
            # Use the git root from state instead of checking if it's a git repo
            git_root = state.git_root
            # logger.debug(f"Using git root from state: {git_root}") # This line was removed as per the new_code
            
            # Build the command with -C flag using the git root from state
            base_cmd = f"git -C {git_root.as_posix()}"

            match command:
                case "status":
                    cmd = f"{base_cmd} status --porcelain"
                
                case "diff":
                    base_commit = arguments.get("base_commit")
                    file_path = arguments.get("file_path")
                    if base_commit and not isinstance(base_commit, str):
                        return ToolExecResult(error="The 'base_commit' parameter must be a string.", error_code=1)
                    if file_path and not isinstance(file_path, str):
                        return ToolExecResult(error="The 'file_path' parameter must be a string.", error_code=1)

                    cmd_parts = [base_cmd, "--no-pager", "diff"]
                    if base_commit:
                        cmd_parts.append(base_commit)
                    if file_path:
                        cmd_parts.append("--")
                        cmd_parts.append(file_path)
                    cmd = " ".join(cmd_parts)

                case "add":
                    add_path = arguments.get("add_path", ".")
                    if not isinstance(add_path, str):
                        return ToolExecResult(error="The 'add_path' parameter must be a string.", error_code=1)
                    cmd = f"{base_cmd} add {add_path}"

                case "commit":
                    message = arguments.get("message")
                    if not message or not isinstance(message, str):
                        return ToolExecResult(error="The 'message' parameter is required for commit.", error_code=1)
                    # Basic protection against command injection in message
                    message = message.replace('"', '\\"')
                    cmd = f'{base_cmd} commit -m "{message}"'

                case "restore":
                    restore_path = arguments.get("restore_path", ".")
                    if not isinstance(restore_path, str):
                        return ToolExecResult(error="The 'restore_path' parameter for restore must be a string.", error_code=1)
                    cmd = f"{base_cmd} restore {restore_path}"
                
                case _:
                    # This case should not be reachable due to the initial check
                    return ToolExecResult(error=f"Unknown command: {command}", error_code=1)

            return_code, stdout, stderr = await run(cmd)
            return ToolExecResult(output=stdout, error=stderr, error_code=return_code)

        except FileNotFoundError:
            # This is less likely to happen now since we are not changing directory
            return ToolExecResult(error=f"The directory does not exist: {path_str}", error_code=1)
        except Exception as e:
            return ToolExecResult(error=f"An unexpected error occurred: {e}", error_code=1)
