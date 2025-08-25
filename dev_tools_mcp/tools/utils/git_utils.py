"""
Git utility functions for tools that need to show git diff after file modifications.
"""

import logging
from pathlib import Path
from typing import Optional

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.run import run
from dev_tools_mcp.utils.path_utils import resolve_path

# Настройка логирования
logger = logging.getLogger(__name__)


async def get_git_diff(file_path: str, fs_state: FileSystemState) -> Optional[str]:
    """
    Get git diff for a file if it's in a git repository.
    
    Args:
        file_path: Path to the file to get diff for (must be relative to fs_state.cwd)
        fs_state: FileSystemState for path resolution
        
    Returns:
        Git diff string if successful, None if not in git repo or no changes
    """
    logger.debug(f"get_git_diff called with file_path={file_path}")
    
    try:
        # Check if we have a git repository in state
        if not fs_state.git_root:
            logger.debug("No git repository found in state")
            return None
        
        # All paths should be relative to the locked directory
        if Path(file_path).is_absolute():
            logger.warning(f"Absolute path provided to get_git_diff: {file_path}, this should not happen")
            # Convert to relative path from cwd
            try:
                rel_path = Path(file_path).relative_to(fs_state.cwd)
                file_path = str(rel_path)
                logger.debug(f"Converted absolute path to relative: {file_path}")
            except ValueError:
                logger.error(f"Cannot convert absolute path {file_path} to relative path from {fs_state.cwd}")
                return None
        
        # Resolve the relative path against the locked directory
        resolved_path = resolve_path(fs_state, file_path, must_be_relative=True)
        logger.debug(f"Resolved relative path: {resolved_path}")
        
        # Use the git root from state
        git_root = fs_state.git_root
        logger.debug(f"Using git root from state: {git_root}")
        
        # Get git diff for the specific file using the relative path from git root
        try:
            # Calculate relative path from git root
            rel_path_from_git_root = resolved_path.relative_to(git_root)
            diff_cmd = f"git -C {git_root.as_posix()} diff -- {rel_path_from_git_root}"
        except ValueError:
            # Fallback to using just the filename
            diff_cmd = f"git -C {git_root.as_posix()} diff -- {resolved_path.name}"
        
        logger.debug(f"Running git diff command: {diff_cmd}")
        return_code, stdout, stderr = await run(diff_cmd)
        logger.debug(f"Git diff result: return_code={return_code}, stdout_length={len(stdout)}, stderr_length={len(stderr) if stderr else 0}")
        
        if return_code == 0 and stdout.strip():
            logger.debug(f"Git diff successful, returning diff of length {len(stdout)}")
            return stdout
        else:
            logger.debug(f"Git diff failed or empty: return_code={return_code}, stdout_empty={not stdout.strip()}")
            return None
        
    except Exception as e:
        logger.error(f"Exception in get_git_diff: {e}")
        # If anything goes wrong, just return None (don't fail the main operation)
        return None
