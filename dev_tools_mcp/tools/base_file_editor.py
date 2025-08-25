# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Base class for file editing tools with common functionality."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import Tool, ToolCallArguments, ToolError, ToolExecResult
from dev_tools_mcp.utils.path_utils import resolve_path

logger = logging.getLogger(__name__)


class BaseFileEditorTool(Tool, ABC):
    """Base class for file editing tools with common functionality."""

    def __init__(self, model_provider: str | None = None) -> None:
        super().__init__(model_provider)
        self._fs_state: FileSystemState | None = None

    def _get_relative_path(self, absolute_path: Path, fs_state: FileSystemState) -> str:
        """
        Get the relative path from the current working directory for display purposes.
        
        Args:
            absolute_path: The absolute path to convert
            fs_state: The current file system state
            
        Returns:
            The relative path as a string, or just the filename if conversion fails
        """
        try:
            return str(absolute_path.relative_to(fs_state.cwd))
        except ValueError:
            # Fallback to just the filename if we can't get relative path
            return absolute_path.name

    def _resolve_and_validate_path(self, path_str: str, fs_state: FileSystemState, 
                                 must_exist: bool = True, allow_directories: bool = False) -> Path:
        """
        Resolve and validate a file path.
        
        Args:
            path_str: The path string to resolve
            fs_state: The current file system state
            must_exist: Whether the path must exist
            allow_directories: Whether directories are allowed
            
        Returns:
            The resolved Path object
            
        Raises:
            ToolError: If validation fails
        """
        try:
            resolved_path = resolve_path(fs_state, path_str, must_be_relative=True)
            logger.debug(f"Resolved path: {resolved_path}")

            if must_exist and not resolved_path.exists():
                rel_path = self._get_relative_path(resolved_path, fs_state)
                raise ToolError(f"The path {rel_path} does not exist.")

            if not allow_directories and resolved_path.is_dir():
                rel_path = self._get_relative_path(resolved_path, fs_state)
                raise ToolError(f"The path {rel_path} is a directory and this operation is not allowed on directories.")

            return resolved_path

        except (ValueError, PermissionError, FileNotFoundError) as e:
            logger.error(f"Error resolving path {path_str}: {e}")
            raise ToolError(f"Error resolving path: {str(e)}") from e

    def _validate_fs_state(self, arguments: ToolCallArguments) -> FileSystemState:
        """
        Validate and extract FileSystemState from arguments.
        
        Args:
            arguments: The tool call arguments
            
        Returns:
            The validated FileSystemState
            
        Raises:
            ToolError: If FileSystemState is not found or invalid
        """
        state = arguments.get("_fs_state")
        if not isinstance(state, FileSystemState):
            logger.error("FileSystemState not found in arguments")
            raise ToolError("FileSystemState not found in arguments.")
        
        self._fs_state = state
        return state

    def read_file(self, path: Path, fs_state: FileSystemState) -> str:
        """
        Read the content of a file from a given path.
        
        Args:
            path: The path to read from
            fs_state: The current file system state
            
        Returns:
            The file content as a string
            
        Raises:
            ToolError: If an error occurs while reading
        """
        logger.debug(f"Reading file: {path}")
        try:
            content = path.read_text()
            logger.debug(f"Successfully read file {path}, content length: {len(content)}")
            return content
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            rel_path = self._get_relative_path(path, fs_state)
            raise ToolError(f"Ran into {e} while trying to read {rel_path}") from None

    def write_file(self, path: Path, content: str, fs_state: FileSystemState) -> None:
        """
        Write content to a file at the given path.
        
        Args:
            path: The path to write to
            content: The content to write
            fs_state: The current file system state
            
        Raises:
            ToolError: If an error occurs while writing
        """
        logger.debug(f"Writing file: {path}, content length: {len(content)}")
        try:
            path.write_text(content)
            logger.debug(f"Successfully wrote file {path}")
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            rel_path = self._get_relative_path(path, fs_state)
            raise ToolError(f"Ran into {e} while trying to write to {rel_path}") from None

    async def _add_git_diff_to_output(self, output_msg: str, file_path: Path, fs_state: FileSystemState) -> str:
        """
        Add git diff to the output message if available.
        
        Args:
            output_msg: The current output message
            file_path: The file path for the git diff
            fs_state: The current file system state
            
        Returns:
            The output message with git diff added if available
        """
        try:
            from dev_tools_mcp.tools.utils import get_git_diff
            
            rel_path = self._get_relative_path(file_path, fs_state)
            git_diff = await get_git_diff(str(rel_path), fs_state)
            
            if git_diff:
                logger.debug(f"Git diff length: {len(git_diff)}")
                output_msg += f"\n\nGit diff for {rel_path}:\n```diff\n{git_diff}\n```"
            else:
                logger.debug("No git diff available or git diff failed")
                
        except Exception as e:
            logger.debug(f"Failed to get git diff: {e}")
            
        return output_msg

    @abstractmethod
    async def _execute_operation(self, arguments: ToolCallArguments, fs_state: FileSystemState) -> ToolExecResult:
        """
        Execute the specific operation for this tool.
        
        Args:
            arguments: The tool call arguments
            fs_state: The current file system state
            
        Returns:
            The result of the operation
        """
        pass

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        """
        Execute the tool with common validation and error handling.
        
        Args:
            arguments: The tool call arguments
            
        Returns:
            The result of the tool execution
        """
        try:
            # Validate FileSystemState
            fs_state = self._validate_fs_state(arguments)
            
            # Execute the specific operation
            return await self._execute_operation(arguments, fs_state)
            
        except ToolError as e:
            logger.error(f"Tool error in {self.get_name()}: {e}")
            return ToolExecResult(error=str(e), error_code=-1)
        except Exception as e:
            logger.error(f"Unexpected error in {self.get_name()}: {e}")
            return ToolExecResult(error=f"Unexpected error: {str(e)}", error_code=-1)
