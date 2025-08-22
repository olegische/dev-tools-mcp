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

import asyncio
from typing import override

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class BashTool(Tool):
    """
    A tool that allows the agent to run bash commands within the session's CWD.
    """

    def __init__(self, model_provider: str | None = None):
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "bash"

    @override
    def get_description(self) -> str:
        return """Run commands in a bash shell inside the locked CWD.
* Each command is executed in a new, clean shell process.
* The shell is started in the CWD that was set by `file_system.lock_cwd()`.
* Please avoid commands that may produce a very large amount of output.
* Please run long lived commands in the background, e.g. 'sleep 10 &' or start a server in the background.
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The bash command to run.",
                required=True,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        state = arguments.get("_fs_state")
        if not isinstance(state, FileSystemState):
            return ToolExecResult(error="FileSystemState not found in arguments.", error_code=-1)

        command = arguments.get("command")
        if not command or not isinstance(command, str):
            return ToolExecResult(error="The 'command' parameter is required.", error_code=-1)

        try:
            # Command is executed in a new process, but with the correct CWD
            full_command = f"cd {state.cwd.resolve()} && {command}"

            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            return ToolExecResult(
                output=stdout.decode(),
                error=stderr.decode(),
                error_code=process.returncode,
            )
        except Exception as e:
            return ToolExecResult(error=f"An unexpected error occurred: {e}", error_code=1)
