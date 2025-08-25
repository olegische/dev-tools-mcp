# Copyright (c) 2023 Anthropic
# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
# This file has been modified by ByteDance Ltd. and/or its affiliates. on 13 June 2025
#
# Original file was released under MIT License, with the full license text
# available at https://github.com/anthropics/anthropic-quickstarts/blob/main/LICENSE
#
# This modified file is released under the same license.

import logging
from pathlib import Path
from typing import override

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import ToolCallArguments, ToolError, ToolExecResult, ToolParameter
from dev_tools_mcp.tools.base_file_editor import BaseFileEditorTool
from dev_tools_mcp.tools.run import maybe_truncate, run

# Настройка логирования
logger = logging.getLogger(__name__)

EditToolSubCommands = [
    "view",
    "create",
    "str_replace",
    "insert",
]
SNIPPET_LINES: int = 4


class TextEditorTool(BaseFileEditorTool):
    """Tool to replace a string in a file."""

    def __init__(self, model_provider: str | None = None) -> None:
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "str_replace_based_edit_tool"

    @override
    def get_description(self) -> str:
        return """Custom editing tool for viewing, creating and editing files
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file !!! If you know that the `path` already exists, please remove it first and then perform the `create` operation!
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
* The `new_str` parameter should contain the edited lines that should replace the `old_str`
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        """Get the parameters for the str_replace_based_edit_tool."""
        return [
            ToolParameter(
                name="command",
                type="string",
                description=f"The commands to run. Allowed options are: {', '.join(EditToolSubCommands)}.",
                required=True,
                enum=EditToolSubCommands,
            ),
            ToolParameter(
                name="file_text",
                type="string",
                description="Required parameter of `create` command, with the content of the file to be created.",
            ),
            ToolParameter(
                name="insert_line",
                type="integer",
                description="Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
            ),
            ToolParameter(
                name="new_str",
                type="string",
                description="Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
            ),
            ToolParameter(
                name="old_str",
                type="string",
                description="Required parameter of `str_replace` command containing the string in `path` to replace.",
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to file or directory, relative to the CWD. e.g. 'src/main.py'.",
                required=True,
            ),
            ToolParameter(
                name="view_range",
                type="array",
                description="Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                items={"type": "integer"},
            ),
        ]



    @override
    async def _execute_operation(self, arguments: ToolCallArguments, fs_state: FileSystemState) -> ToolExecResult:
        """Execute the text editor operation."""
        command = str(arguments.get("command"))
        path_str = str(arguments.get("path"))
        logger.debug(f"Processing command '{command}' for path '{path_str}'")

        # Resolve and validate path based on command
        if command == "create":
            resolved_path = self._resolve_and_validate_path(path_str, fs_state, must_exist=False, allow_directories=False)
            if resolved_path.exists():
                rel_path = self._get_relative_path(resolved_path, fs_state)
                raise ToolError(f"File already exists at: {rel_path}.")
        elif command == "view":
            resolved_path = self._resolve_and_validate_path(path_str, fs_state, must_exist=True, allow_directories=True)
        else:  # str_replace, insert
            resolved_path = self._resolve_and_validate_path(path_str, fs_state, must_exist=True, allow_directories=False)

        logger.debug(f"Executing command '{command}' for path '{resolved_path}'")
        match command:
            case "view":
                logger.debug("Calling _view_handler")
                return await self._view_handler(arguments, resolved_path, fs_state)
            case "create":
                logger.debug("Calling _create_handler")
                return await self._create_handler(arguments, resolved_path, fs_state)
            case "str_replace":
                logger.debug("Calling _str_replace_handler")
                return await self._str_replace_handler(arguments, resolved_path, fs_state)
            case "insert":
                logger.debug("Calling _insert_handler")
                return await self._insert_handler(arguments, resolved_path, fs_state)
            case _:
                logger.error(f"Unrecognized command: {command}")
                return ToolExecResult(
                    error=f"Unrecognized command {command}. The allowed commands for the {self.get_name()} tool are: {', '.join(EditToolSubCommands)}",
                    error_code=-1,
                )

    async def _view(self, path: Path, view_range: list[int] | None = None, fs_state=None) -> ToolExecResult:
        """Implement the view command"""
        if path.is_dir():
            if view_range:
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )

            # Get relative path for display
            rel_path = self._get_relative_path(path, fs_state)

            return_code, stdout, stderr = await run(rf"find {path} -maxdepth 2 -not -path '*/\.*'")
            if not stderr:
                stdout = f"Here's the files and directories up to 2 levels deep in {rel_path}, excluding hidden items:\n{stdout}\n"
            return ToolExecResult(error_code=return_code, output=stdout, error=stderr)

        file_content = self.read_file(path, fs_state)
        init_line = 1
        if view_range:
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ToolError("Invalid `view_range`. It should be a list of two integers.")
            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within the range of lines of the file: {[1, n_lines_file]}"
                )
            if final_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be smaller than the number of lines in the file: `{n_lines_file}`"
                )
            if final_line != -1 and final_line < init_line:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be larger or equal than its first `{init_line}`"
                )

            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        # Get relative path for display
        rel_path = self._get_relative_path(path, fs_state)

        return ToolExecResult(
            output=self._make_output(file_content, str(rel_path), init_line=init_line)
        )

    async def str_replace(self, path: Path, old_str: str, new_str: str | None, fs_state) -> ToolExecResult:
        """Implement the str_replace command, which replaces old_str with new_str in the file content"""
        logger.debug(f"str_replace called with path={path}, old_str length={len(old_str)}, new_str length={len(new_str) if new_str else 0}")
        
        # Read the file content
        file_content = self.read_file(path, fs_state).expandtabs()
        logger.debug(f"File content read, length: {len(file_content)}")
        
        # Convert \n to actual newlines in old_str for proper matching
        old_str_normalized = old_str.replace('\\n', '\n').expandtabs()
        new_str_normalized = new_str.replace('\\n', '\n').expandtabs() if new_str is not None else ""

        # Check if old_str is unique in the file
        occurrences = file_content.count(old_str_normalized)
        logger.debug(f"Found {occurrences} occurrences of old_str in file")
        
        if occurrences == 0:
            # Try to find the string with original \n as fallback
            occurrences_fallback = file_content.count(old_str)
            if occurrences_fallback > 0:
                logger.debug(f"Found {occurrences_fallback} occurrences with original \\n format, using that")
                old_str_normalized = old_str
                occurrences = occurrences_fallback
            else:
                # Get relative path for error message
                rel_path = self._get_relative_path(path, fs_state)
                raise ToolError(
                    f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {rel_path}."
                )
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [idx + 1 for idx, line in enumerate(file_content_lines) if old_str_normalized in line]
            # Get relative path for error message
            rel_path = self._get_relative_path(path, fs_state)
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str `{old_str_normalized}` in lines {lines} in {rel_path}. Please ensure it is unique"
            )

        # Replace old_str with new_str
        new_file_content = file_content.replace(old_str_normalized, new_str_normalized)
        logger.debug(f"String replacement completed, new file content length: {len(new_file_content)}")

        # Write the new content to the file
        self.write_file(path, new_file_content, fs_state)
        logger.debug(f"File written successfully to {path}")

        # Create a snippet of the edited section
        replacement_line = file_content.split(old_str_normalized)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str_normalized.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        # Get relative path from fs_state.cwd for display
        rel_path = self._get_relative_path(path, fs_state)

        # Prepare the success message with relative path
        success_msg = f"The file {rel_path} has been edited. "
        success_msg += self._make_output(snippet, f"a snippet of {rel_path}", start_line + 1)
        success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

        # Add git diff if available
        success_msg = await self._add_git_diff_to_output(success_msg, path, fs_state)

        return ToolExecResult(
            output=success_msg,
        )

    async def _insert(self, path: Path, insert_line: int, new_str: str, fs_state) -> ToolExecResult:
        """Implement the insert command, which inserts new_str at the specified line in the file content."""
        logger.debug(f"_insert called with path={path}, insert_line={insert_line}, new_str length={len(new_str)}")
        
        file_text = self.read_file(path, fs_state).expandtabs()
        logger.debug(f"File content read, length: {len(file_text)}")
        
        # Convert \n to actual newlines in new_str for proper insertion
        new_str_normalized = new_str.replace('\\n', '\n').expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)
        logger.debug(f"File has {n_lines_file} lines")

        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"Invalid `insert_line` parameter: {insert_line}. It should be within the range of lines of the file: {[0, n_lines_file]}"
            )

        new_str_lines = new_str_normalized.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line] + new_str_lines + file_text_lines[insert_line:]
        )
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )

        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        self.write_file(path, new_file_text, fs_state)
        logger.debug(f"File written successfully to {path}")

        # Get relative path from fs_state.cwd for display
        rel_path = self._get_relative_path(path, fs_state)

        success_msg = f"The file {rel_path} has been edited. "
        success_msg += self._make_output(
            snippet,
            "a snippet of the edited file",
            max(1, insert_line - SNIPPET_LINES + 1),
        )
        success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."
        
        # Add git diff if available
        success_msg = await self._add_git_diff_to_output(success_msg, path, fs_state)
            
        return ToolExecResult(
            output=success_msg,
        )

    # Note: undo_edit method is not implemented in this version as it was removed



    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ):
        """Generate output for the CLI based on the content of a file."""
        file_content = maybe_truncate(file_content)
        if expand_tabs:
            file_content = file_content.expandtabs()
        file_content = "\n".join(
            [f"{i + init_line:6}\t{line}" for i, line in enumerate(file_content.split("\n"))]
        )
        return (
            f"Here's the result of running `cat -n` on {file_descriptor}:\n" + file_content + "\n"
        )

    async def _view_handler(self, arguments: ToolCallArguments, _path: Path, fs_state) -> ToolExecResult:
        view_range = arguments.get("view_range", None)
        if view_range is None:
            return await self._view(_path, None, fs_state)
        if not (isinstance(view_range, list) and all(isinstance(i, int) for i in view_range)):
            return ToolExecResult(
                error="Parameter `view_range` should be a list of integers.",
                error_code=-1,
            )
        view_range_int: list[int] = [i for i in view_range if isinstance(i, int)]
        return await self._view(_path, view_range_int, fs_state)

    async def _create_handler(self, arguments: ToolCallArguments, _path: Path, fs_state) -> ToolExecResult:
        logger.debug(f"_create_handler called with path={_path}, file_text length={len(arguments.get('file_text', '')) if arguments.get('file_text') else 0}")
        
        file_text = arguments.get("file_text", None)
        if not isinstance(file_text, str):
            return ToolExecResult(
                error="Parameter `file_text` is required and must be a string for command: create",
                error_code=-1,
            )
        
        # Convert \n to actual newlines in file_text for proper file creation
        file_text_normalized = file_text.replace('\\n', '\n')
        
        # Validate JSON if file has .json extension
        if _path.suffix.lower() == '.json':
            try:
                import json
                json.loads(file_text_normalized)
                logger.debug("JSON validation successful")
            except json.JSONDecodeError as e:
                logger.debug(f"JSON validation failed: {e}")
                return ToolExecResult(
                    error=f"Invalid JSON content: {str(e)}",
                    error_code=-1,
                )
        
        self.write_file(_path, file_text_normalized, fs_state)
        logger.debug(f"File created successfully at {_path}")
        
        # Get relative path from fs_state.cwd for display
        rel_path = self._get_relative_path(_path, fs_state)
        
        output_msg = f"File created successfully at: {rel_path}"
        
        # For new files, show the file content instead of git diff
        # Git diff won't work for untracked files (they don't exist in git yet)
        # This follows the same pattern as file_system.read for consistency
        logger.debug(f"New file created, showing file content instead of git diff for {rel_path}")
        try:
            # Read the file content using the same logic as file_system.read
            file_content = self.read_file(_path, fs_state)
            # Truncate if too long (similar to _make_output logic)
            if len(file_content) > 1000:
                file_content = file_content[:1000] + "\n... [truncated]"
            output_msg += f"\n\nFile content:\n```\n{file_content}\n```"
        except Exception as e:
            logger.debug(f"Failed to read file content: {e}")
            output_msg += f"\n\nFile created successfully (content preview not available)"
            
        return ToolExecResult(output=output_msg)

    async def _str_replace_handler(self, arguments: ToolCallArguments, _path: Path, fs_state) -> ToolExecResult:
        logger.debug(f"_str_replace_handler called with path={_path}")
        
        old_str = arguments.get("old_str") if "old_str" in arguments else None
        logger.debug(f"old_str parameter: {'present' if old_str else 'missing'}, type: {type(old_str)}")
        
        if not isinstance(old_str, str):
            logger.error(f"old_str parameter is not a string: {type(old_str)}")
            return ToolExecResult(
                error="Parameter `old_str` is required and should be a string for command: str_replace",
                error_code=-1,
            )
        new_str = arguments.get("new_str") if "new_str" in arguments else None
        logger.debug(f"new_str parameter: {'present' if new_str else 'missing'}, type: {type(new_str)}")
        
        if not (new_str is None or isinstance(new_str, str)):
            logger.error(f"new_str parameter is not a string or None: {type(new_str)}")
            return ToolExecResult(
                error="Parameter `new_str` should be a string or null for command: str_replace",
                error_code=-1,
            )
        
        logger.debug(f"Calling str_replace with old_str length={len(old_str)}, new_str length={len(new_str) if new_str else 0}")
        return await self.str_replace(_path, old_str, new_str, fs_state)

    async def _insert_handler(self, arguments: ToolCallArguments, _path: Path, fs_state) -> ToolExecResult:
        logger.debug(f"_insert_handler called with path={_path}")
        
        insert_line = arguments.get("insert_line") if "insert_line" in arguments else None
        logger.debug(f"insert_line parameter: {'present' if insert_line is not None else 'missing'}, value: {insert_line}, type: {type(insert_line)}")
        
        if insert_line is None:
            logger.error("insert_line parameter is missing")
            return ToolExecResult(
                error="Parameter `insert_line` is required for command: insert",
                error_code=-1,
            )
        
        # Convert to int if it's a string
        if isinstance(insert_line, str):
            try:
                insert_line = int(insert_line)
                logger.debug(f"Converted insert_line from string to int: {insert_line}")
            except ValueError:
                logger.error(f"Failed to convert insert_line to int: {insert_line}")
                return ToolExecResult(
                    error=f"Parameter `insert_line` must be a valid integer, got: {insert_line}",
                    error_code=-1,
                )
        elif not isinstance(insert_line, int):
            logger.error(f"insert_line parameter is not an integer: {type(insert_line)}")
            return ToolExecResult(
                error=f"Parameter `insert_line` must be an integer, got: {type(insert_line).__name__}",
                error_code=-1,
            )
            
        new_str_to_insert = arguments.get("new_str") if "new_str" in arguments else None
        logger.debug(f"new_str parameter: {'present' if new_str_to_insert else 'missing'}, type: {type(new_str_to_insert)}")
        
        if not isinstance(new_str_to_insert, str):
            logger.error(f"new_str parameter is not a string: {type(new_str_to_insert)}")
            return ToolExecResult(
                error="Parameter `new_str` is required for command: insert",
                error_code=-1,
            )
        
        logger.debug(f"Calling _insert with insert_line={insert_line}, new_str length={len(new_str_to_insert)}")
        return await self._insert(_path, insert_line, new_str_to_insert, fs_state)
