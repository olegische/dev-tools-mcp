import os
from pathlib import Path
from typing import override

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.utils.path_utils import resolve_path

from .base import Tool, ToolCallArguments, ToolError, ToolExecResult, ToolParameter

FileSystemToolSubCommands = ["cd", "pwd", "ls", "read", "lock_cwd", "unlock_cwd"]


class FileSystemTool(Tool):
    """
    Tool for exploring the file system and managing the session state.
    This is the primary tool for the 'discovery' phase of the workflow.
    It allows for read-only operations to navigate directories and view files.
    It also provides the `lock_cwd` command to transition to the 'edit' phase.
    """

    def __init__(self, model_provider: str | None = None) -> None:
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "file_system"

    @override
    def get_description(self) -> str:
        return """A tool for exploring the file system and managing the session state.
In 'discovery' phase, it provides read-only commands to navigate (`cd`, `ls`, `pwd`) and inspect files (`read`).
Use the `lock_cwd` command to finalize the current working directory and switch to the 'edit' phase, which enables all other tools.
Use the `unlock_cwd` command to switch back to the 'discovery' phase from the 'edit' phase."""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="subcommand",
                type="string",
                description=f"The command to run. Allowed options are: {', '.join(FileSystemToolSubCommands)}.",
                required=True,
                enum=FileSystemToolSubCommands,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Relative or absolute path for the command.",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        state = arguments.get("_fs_state")
        if not isinstance(state, FileSystemState):
            return ToolExecResult(
                error="FileSystemState not found in arguments. This is an internal server error.",
                error_code=-1,
            )

        subcommand = arguments.get("subcommand")
        if not isinstance(subcommand, str):
            return ToolExecResult(error="Subcommand must be a string.", error_code=-1)

        try:
            match subcommand:
                case "pwd":
                    return self._pwd_handler(state)
                case "cd":
                    return self._cd_handler(state, arguments)
                case "ls":
                    return self._ls_handler(state, arguments)
                case "read":
                    return self._read_handler(state, arguments)
                case "lock_cwd":
                    return self._lock_cwd_handler(state)
                case "unlock_cwd":
                    return self._unlock_cwd_handler(state)
                case _:
                    return ToolExecResult(error=f"Unknown subcommand: {subcommand}", error_code=-1)
        except (ToolError, ValueError, PermissionError, NotADirectoryError, FileNotFoundError) as e:
            return ToolExecResult(error=str(e), error_code=-1)

    def _pwd_handler(self, state: FileSystemState) -> ToolExecResult:
        return ToolExecResult(output=str(state.cwd))

    def _cd_handler(self, state: FileSystemState, args: ToolCallArguments) -> ToolExecResult:
        path = args.get("path")
        if not isinstance(path, str):
            raise ValueError("Path is required for cd and must be a string.")
        
        target_dir = resolve_path(state, path)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{target_dir}' is not a directory.")
        
        state.cwd = target_dir
        return ToolExecResult(output=f"CWD is now {state.cwd}")

    def _ls_handler(self, state: FileSystemState, args: ToolCallArguments) -> ToolExecResult:
        path_str = args.get("path", ".")
        if not isinstance(path_str, str):
             raise ValueError("Path must be a string.")

        target_dir = resolve_path(state, path_str)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{target_dir}' is not a directory.")
        
        entries = []
        for entry in os.scandir(target_dir):
            entry_type = "d" if entry.is_dir() else "f"
            entries.append(f"{entry_type} {entry.name}")
        
        return ToolExecResult(output="\n".join(entries))

    def _read_handler(self, state: FileSystemState, args: ToolCallArguments) -> ToolExecResult:
        path = args.get("path")
        if not isinstance(path, str):
            raise ValueError("Path is required for read and must be a string.")

        target_file = resolve_path(state, path)
        if not target_file.is_file():
            raise FileNotFoundError(f"'{target_file}' is not a file or does not exist.")
        
        content = target_file.read_text()
        return ToolExecResult(output=content)

    def _lock_cwd_handler(self, state: FileSystemState) -> ToolExecResult:
        if state.phase == "edit":
            raise ToolError("Already in 'edit' phase.")
        state.phase = "edit"
        return ToolExecResult(
            output=f"Phase changed to 'edit'. CWD is locked at {state.cwd}. Editing tools are now available."
        )

    def _unlock_cwd_handler(self, state: FileSystemState) -> ToolExecResult:
        if state.phase == "discovery":
            raise ToolError("Already in 'discovery' phase.")
        state.phase = "discovery"
        return ToolExecResult(
            output="Phase changed to 'discovery'. Editing tools are now disabled."
        )
