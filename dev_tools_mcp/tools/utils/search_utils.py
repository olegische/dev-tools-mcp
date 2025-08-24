import os
from typing import List

from .constants import MAX_SEARCH_RESULTS, MAX_RIPGREP_MB, MAX_BYTE_SIZE, DEFAULT_IGNORE_FILES


class SearchResult:
    def __init__(self, file_path, line, column, match, before, after):
        self.file_path = file_path
        self.line = line
        self.column = column
        self.match = match
        self.before_context = before
        self.after_context = after


def search_files_with_hypergrep(dir_path: str, query: str, file_pattern: str | None, cwd: str) -> List[SearchResult]:
    """Search files using hypergrep with .gitignore support - твой код."""
    try:
        from hypergrep import grep
    except ImportError:
        raise ImportError("hypergrep not available. Please install it with: pip install hypergrep")
    
    results: List[SearchResult] = []
    
    # Собираем все игнор-файлы
    ignore_files = []
    from .path_utils import collect_gitignores
    ignore_files.extend(collect_gitignores(dir_path))
    for fname in DEFAULT_IGNORE_FILES:
        path = os.path.join(dir_path, fname)
        if os.path.isfile(path):
            ignore_files.append(path)

    try:
        matches = grep(
            query,
            paths=[dir_path],
            include=[file_pattern] if file_pattern else ["*"],
            context=1,               # 1 строка до/после
            with_filename=True,
            with_lineno=True,
            ignore_files=ignore_files,
            hidden=False,   # false → игнорим скрытые
        )

        for m in matches:
            before = [ctx.line for ctx in m.before]
            after = [ctx.line for ctx in m.after]

            results.append(SearchResult(
                file_path=m.path,
                line=m.lineno,
                column=m.colno or 0,
                match=m.line,
                before=before,
                after=after,
            ))

            if len(results) >= MAX_SEARCH_RESULTS:
                break

    except Exception as e:
        raise RuntimeError(f"Error during search: {str(e)}")

    return results
