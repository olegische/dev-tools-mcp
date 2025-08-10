# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from pathlib import Path
from threading import Lock

from dev_tools_mcp.tools.ckg.ckg_database import CKGDatabase

class CKGManager:
    """
    Manages the lifecycle of CKGDatabase instances.

    This class ensures that only one CKGDatabase instance exists per codebase path,
    acting as a singleton manager for database connections. It uses a lock to ensure
    thread-safe creation of new database instances.
    """
    _instances: dict[Path, CKGDatabase]
    _lock: Lock

    def __init__(self):
        self._instances = {}
        self._lock = Lock()

    def get_database(self, codebase_path: Path) -> CKGDatabase:
        """
        Retrieves the CKGDatabase instance for a given codebase path.

        If an instance does not exist for the path, it is created and cached
        in a thread-safe manner.

        Args:
            codebase_path: The absolute path to the codebase.

        Returns:
            The singleton CKGDatabase instance for the given path.
        """
        codebase_path = codebase_path.absolute()
        
        # First, check without a lock for performance
        instance = self._instances.get(codebase_path)
        if instance is None:
            # If not found, acquire a lock to prevent race conditions
            with self._lock:
                # Double-check if another thread created it while we were waiting for the lock
                instance = self._instances.get(codebase_path)
                if instance is None:
                    print(f"Creating new CKGDatabase instance for: {codebase_path}")
                    instance = CKGDatabase(codebase_path)
                    self._instances[codebase_path] = instance
        return instance
