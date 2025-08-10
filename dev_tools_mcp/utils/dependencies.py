"""
Configuration and dependency management for the Dev Tools MCP server.
"""

import logging
from functools import lru_cache

from fastapi import Depends

from dev_tools_mcp.utils.config import ServiceConfig

logger = logging.getLogger(__name__)


@lru_cache
def get_base_config() -> ServiceConfig:
    """
    Retrieves the base server configuration from environment variables.

    This function is cached to avoid repeatedly reading and parsing environment
    variables and .env files, which improves performance.

    Returns:
        A cached instance of the ServiceConfig.
    """
    return ServiceConfig()


# --- Tool Providers ---
# Dependency injection providers for each tool will be defined here.
# This allows for clean separation of concerns and easy testing.

from ..tools.bash_tool import BashTool
from ..tools.edit_tool import TextEditorTool
from ..tools.json_edit_tool import JSONEditTool
from ..tools.ckg_tool import CKGTool
from ..tools.ckg.ckg_manager import CKGManager
from ..tools.git_tool import GitTool
from ..tools.sequential_thinking_tool import SequentialThinkingTool
from ..tools.task_done_tool import TaskDoneTool


@lru_cache
def get_bash_tool_provider() -> BashTool:
    """Returns a cached instance of the BashTool."""
    logger.info("Initializing BashTool singleton.")
    return BashTool()


@lru_cache
def get_file_editor_tool_provider() -> TextEditorTool:
    """Returns a cached instance of the TextEditorTool."""
    logger.info("Initializing TextEditorTool singleton.")
    return TextEditorTool()


@lru_cache
def get_json_editor_tool_provider() -> JSONEditTool:
    """Returns a cached instance of the JSONEditTool."""
    logger.info("Initializing JSONEditTool singleton.")
    return JSONEditTool()


# CKG Related dependencies
# The CKG Manager is a singleton that manages all CKGDatabase instances.
@lru_cache
def get_ckg_manager() -> CKGManager:
    """Returns a singleton instance of the CKGManager."""
    logger.info("Initializing CKGManager singleton.")
    return CKGManager()


@lru_cache
def get_code_search_tool_provider(
    ckg_manager: CKGManager = Depends(get_ckg_manager),
) -> CKGTool:
    """
    Returns a cached instance of the CKGTool, using FastAPI's dependency
    injection to provide the CKGManager.
    """
    logger.info("Initializing CKGTool singleton with CKGManager dependency.")
    return CKGTool(ckg_manager=ckg_manager)


@lru_cache
def get_git_tool_provider() -> GitTool:
    """Returns a cached instance of the GitTool."""
    logger.info("Initializing GitTool singleton.")
    return GitTool()


@lru_cache
def get_sequential_thinking_tool_provider() -> SequentialThinkingTool:
    """Returns a cached instance of the SequentialThinkingTool."""
    logger.info("Initializing SequentialThinkingTool singleton.")
    return SequentialThinkingTool()


@lru_cache
def get_task_done_tool_provider() -> TaskDoneTool:
    """Returns a cached instance of the TaskDoneTool."""
    logger.info("Initializing TaskDoneTool singleton.")
    return TaskDoneTool()
