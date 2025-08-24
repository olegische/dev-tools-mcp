import os
import pathlib


def is_restricted_path(path: pathlib.Path) -> bool:
    """Check if path is restricted (root or home directory) - как в твоем TS коде."""
    try:
        absolute_path = path.resolve()
        
        # Проверка на root директорию
        if os.name == 'nt':  # Windows
            root = pathlib.Path(absolute_path.drive + '\\')
        else:  # Unix-like
            root = pathlib.Path('/')
        
        if absolute_path == root:
            return True
        
        # Проверка на home директорию
        home_dir = pathlib.Path.home()
        if absolute_path == home_dir:
            return True
            
    except (OSError, RuntimeError):
        pass
        
    return False


def collect_gitignores(root: str) -> list[str]:
    """Рекурсивно ищет все .gitignore в дереве начиная с root - твой код."""
    ignore_files = []
    for dirpath, _, filenames in os.walk(root):
        if ".gitignore" in filenames:
            ignore_files.append(os.path.join(dirpath, ".gitignore"))
    return ignore_files
