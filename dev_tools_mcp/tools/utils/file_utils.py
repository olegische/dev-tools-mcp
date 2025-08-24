import os
import pathlib
import stat
from datetime import datetime
from typing import Dict, List, Tuple

from .constants import DEFAULT_IGNORE_DIRECTORIES


def should_ignore_path(path: pathlib.Path) -> bool:
    """Check if a path should be ignored."""
    # Ignore hidden files/directories
    if path.name.startswith('.'):
        return True
    
    # Ignore standard development directories
    if path.name in DEFAULT_IGNORE_DIRECTORIES:
        return True
    
    return False


def get_file_info(file_path: pathlib.Path) -> Dict:
    """Get detailed information about a file."""
    try:
        stat_info = file_path.stat()
        
        # Format file size
        size = stat_info.st_size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
        
        # Format modification time
        mtime = datetime.fromtimestamp(stat_info.st_mtime)
        time_str = mtime.strftime("%Y-%m-%d %H:%M")
        
        # Format permissions
        mode = stat_info.st_mode
        perms = ""
        perms += "r" if mode & stat.S_IRUSR else "-"
        perms += "w" if mode & stat.S_IWUSR else "-"
        perms += "x" if mode & stat.S_IXUSR else "-"
        perms += "r" if mode & stat.S_IRGRP else "-"
        perms += "w" if mode & stat.S_IWGRP else "-"
        perms += "x" if mode & stat.S_IXGRP else "-"
        perms += "r" if mode & stat.S_IROTH else "-"
        perms += "w" if mode & stat.S_IWOTH else "-"
        perms += "x" if mode & stat.S_IXOTH else "-"
        
        return {
            "name": file_path.name,
            "is_dir": file_path.is_dir(),
            "size": size_str,
            "modified": time_str,
            "permissions": perms,
            "path": str(file_path),
            "raw_size": size,
            "raw_mtime": stat_info.st_mtime
        }
        
    except (PermissionError, OSError):
        return {
            "name": file_path.name,
            "is_dir": file_path.is_dir(),
            "size": "?",
            "modified": "?",
            "permissions": "?",
            "path": str(file_path),
            "raw_size": 0,
            "raw_mtime": 0
        }



