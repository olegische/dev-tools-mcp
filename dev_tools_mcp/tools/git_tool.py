import os
from pathlib import Path
from typing import override

from dev_tools_mcp.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter
from dev_tools_mcp.tools.run import run


class GitTool(Tool):
    """Tool for interacting with Git repositories."""

    @override
    def get_name(self) -> str:
        return "git_diff"

    @override
    def get_description(self) -> str:
        return """
        Gets the git diff of a project.
        Can show current uncommitted changes or changes relative to a specific commit.
        """

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="The absolute path to the Git repository.",
                required=True,
            ),
            ToolParameter(
                name="base_commit",
                type="string",
                description="The commit hash to diff against. If not provided, shows current uncommitted changes.",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        path_str = arguments.get("path")
        if not path_str or not isinstance(path_str, str):
            return ToolExecResult(error="The 'path' parameter is required.", error_code=1)

        base_commit = arguments.get("base_commit")
        if base_commit and not isinstance(base_commit, str):
            return ToolExecResult(error="The 'base_commit' parameter must be a string.", error_code=1)

        repo_path = Path(path_str)
        if not repo_path.is_dir():
            return ToolExecResult(error=f"The provided path is not a directory: {path_str}", error_code=1)

        pwd = os.getcwd()
        try:
            os.chdir(repo_path)
            
            # Check if it's a git repository
            is_git_repo_code, _, is_git_repo_err = await run("git rev-parse --is-inside-work-tree")
            if is_git_repo_code != 0:
                return ToolExecResult(error=f"The directory is not a git repository: {path_str}. Error: {is_git_repo_err}", error_code=1)

            if not base_commit:
                command = "git --no-pager diff"
            else:
                command = f"git --no-pager diff {base_commit} HEAD"
            
            return_code, stdout, stderr = await run(command)
            return ToolExecResult(output=stdout, error=stderr, error_code=return_code)

        except FileNotFoundError:
            return ToolExecResult(error=f"The directory does not exist: {path_str}", error_code=1)
        except Exception as e:
            return ToolExecResult(error=f"An unexpected error occurred: {e}", error_code=1)
        finally:
            os.chdir(pwd)
