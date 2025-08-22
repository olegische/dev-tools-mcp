from dev_tools_mcp.models.session import FileSystemState


class SessionManager:
    """Manages file system states for all user sessions."""

    def __init__(self) -> None:
        # Simple dict as an in-process session storage.
        # For a real application, this could be Redis or another persistent store.
        self._storage: dict[str, FileSystemState] = {}

    def get_fs_state(self, session_id: str = "default") -> FileSystemState:
        """Returns or creates the state for a given session."""
        if session_id not in self._storage:
            self._storage[session_id] = FileSystemState()
        return self._storage[session_id]
