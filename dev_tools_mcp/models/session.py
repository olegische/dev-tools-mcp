from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FileSystemState(BaseModel):
    """Stores the file system state for a single session."""

    root: Path = Field(default=Path("/"))
    cwd: Path | None = None
    phase: Literal["discovery", "edit"] = "discovery"
    git_root: Path | None = None  # Path to git repository root

    def model_post_init(self, __context) -> None:
        if self.cwd is None:
            self.cwd = self.root
