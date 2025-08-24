import pathlib
from collections import deque
from typing import override

from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.utils.path_utils import resolve_path

from .base import Tool, ToolCallArguments, ToolError, ToolExecResult, ToolParameter
from .utils.file_utils import get_file_info
from .utils.path_utils import is_restricted_path
from .utils.formatting_utils import format_file_list, format_tree, format_search_results
from .utils.search_utils import search_files_with_hypergrep, SearchResult
from .utils.constants import MAX_SEARCH_RESULTS, MAX_RIPGREP_MB, MAX_BYTE_SIZE, DEFAULT_FILE_LIMIT

DirectoryExplorerSubCommands = ["list", "tree", "search"]


class DirectoryExplorerTool(Tool):
    """
    Advanced tool for exploring directory structures with detailed information.
    
    This tool provides comprehensive directory analysis capabilities including:
    - Detailed file listing with sizes, dates, and permissions
    - Tree-like directory structure visualization
    - Content-based file searching using hypergrep with .gitignore support
    
    The tool supports both single-level and recursive directory traversal using
    breadth-first search (BFS) to ensure files at all levels are discovered.
    
    Security features:
    - Blocks access to root (/) and home (~) directories
    - Automatically ignores hidden files and common development directories
    - Respects .gitignore files for search operations
    
    Available in both 'discovery' and 'edit' phases of the MCP workflow.
    """

    def __init__(self, model_provider: str | None = None) -> None:
        """
        Initialize the DirectoryExplorerTool.
        
        Args:
            model_provider: Optional model provider identifier for tool configuration.
                          If None, uses default provider settings.
        """
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        """
        Get the model provider associated with this tool.
        
        Returns:
            The model provider identifier string, or None if not configured.
        """
        return self._model_provider

    @override
    def get_name(self) -> str:
        """
        Get the tool name for MCP registration.
        
        Returns:
            The tool name as a string: "directory_explorer".
        """
        return "directory_explorer"

    @override
    def get_description(self) -> str:
        """
        Get the tool description for MCP discovery.
        
        Returns:
            A detailed description of the tool's capabilities and usage.
        """
        return """Advanced tool for exploring directory structures with detailed information.
Provides comprehensive directory analysis including:
- 'list': Detailed file listing with sizes, dates, and permissions
- 'tree': Tree-like directory structure visualization
- 'search': Search file contents using grep-like functionality with .gitignore support

Supports recursive traversal with intelligent filtering of common development directories."""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        """
        Get the tool's parameter schema for MCP registration.
        
        Returns:
            A list of ToolParameter objects defining the tool's interface.
        """
        return [
            ToolParameter(
                name="subcommand",
                type="string",
                description=f"The command to run. Allowed options are: {', '.join(DirectoryExplorerSubCommands)}.",
                required=True,
                enum=DirectoryExplorerSubCommands,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Relative or absolute path for the command. Defaults to current directory.",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="Whether to traverse directories recursively (for list and tree commands).",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description=f"Maximum number of files to return (for list and tree commands). Default: {DEFAULT_FILE_LIMIT}",
                required=False,
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search query for the 'search' command.",
                required=False,
            ),
            ToolParameter(
                name="file_pattern",
                type="string",
                description="File pattern to search in (e.g., '*.py', '*.js'). Default: all files.",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        """
        Execute the directory explorer tool command.
        
        This method routes the command to the appropriate handler based on the subcommand.
        All commands perform security checks to prevent access to restricted directories.
        
        Args:
            arguments: ToolCallArguments containing the command parameters and session state.
                     Must include 'subcommand' and optionally 'path', 'recursive', 'limit',
                     'query', and 'file_pattern' depending on the subcommand.
        
        Returns:
            ToolExecResult containing either the command output or error information.
        
        Raises:
            ToolError: If the subcommand is unknown or invalid.
            ValueError: If required parameters are missing or invalid.
            PermissionError: If access to the target directory is denied.
            NotADirectoryError: If the target path is not a directory.
            FileNotFoundError: If the target path does not exist.
        """
        state = arguments.get("_fs_state")
        if not isinstance(state, FileSystemState):
            return ToolExecResult(
                error="FileSystemState not found in arguments. This is an internal server error.",
                error_code=-1,
            )

        subcommand = arguments.get("subcommand")
        if not isinstance(subcommand, str):
            return ToolExecResult(error="Subcommand must be a string.", error_code=-1)

        try:
            match subcommand:
                case "list":
                    return self._list_handler(state, arguments)
                case "tree":
                    return self._tree_handler(state, arguments)
                case "search":
                    return self._search_handler(state, arguments)
                case _:
                    return ToolExecResult(error=f"Unknown subcommand: {subcommand}", error_code=-1)
        except (ToolError, ValueError, PermissionError, NotADirectoryError, FileNotFoundError) as e:
            return ToolExecResult(error=str(e), error_code=-1)

    def _list_handler(self, state: FileSystemState, args: ToolCallArguments) -> ToolExecResult:
        """
        Handle the 'list' command with detailed file information.
        
        This command provides a comprehensive listing of files and directories with
        detailed metadata including file sizes, modification dates, and permissions.
        Supports both single-level and recursive traversal using breadth-first search.
        
        The command automatically filters out hidden files and common development
        directories (node_modules, __pycache__, etc.) to provide clean output.
        
        Args:
            state: The current file system session state containing CWD information.
            args: ToolCallArguments containing:
                - path: Target directory path (defaults to current directory)
                - recursive: Whether to traverse subdirectories
                - limit: Maximum number of files to return
        
        Returns:
            ToolExecResult containing a formatted list of files with metadata.
        
        Raises:
            ValueError: If path parameter is invalid.
            NotADirectoryError: If target path is not a directory.
            PermissionError: If access to target directory is denied.
        """
        path_str = args.get("path", ".")
        if not isinstance(path_str, str):
            raise ValueError("Path must be a string.")

        recursive = args.get("recursive", False)
        if not isinstance(recursive, bool):
            recursive = False

        limit = args.get("limit", DEFAULT_FILE_LIMIT)
        if not isinstance(limit, int) or limit <= 0:
            limit = DEFAULT_FILE_LIMIT

        target_dir = resolve_path(state, path_str)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{target_dir}' is not a directory.")

        # Проверка на root/home директории
        if is_restricted_path(target_dir):
            return ToolExecResult(output="Access denied: Cannot list files in root or home directory.")

        if recursive:
            files, reached_limit = self._list_files_recursive(target_dir, limit)
        else:
            files, reached_limit = self._list_files_single_level(target_dir, limit)

        output = format_file_list(files)
        if reached_limit:
            output += f"\n\n... and {len(files)} more files (limit reached)"
        
        return ToolExecResult(output=output)

    def _tree_handler(self, state: FileSystemState, args: ToolCallArguments) -> ToolExecResult:
        """
        Handle the 'tree' command with tree-like visualization.
        
        This command creates a hierarchical tree representation of the directory
        structure, similar to the Unix 'tree' command. Each level is properly
        indented and shows whether items are files or directories.
        
        The tree is built using breadth-first traversal to ensure consistent
        level-by-level processing and to avoid missing deeply nested directories.
        
        Args:
            state: The current file system session state containing CWD information.
            args: ToolCallArguments containing:
                - path: Target directory path (defaults to current directory)
                - recursive: Whether to traverse subdirectories
                - limit: Maximum number of items to display
        
        Returns:
            ToolExecResult containing a formatted tree structure.
        
        Raises:
            ValueError: If path parameter is invalid.
            NotADirectoryError: If target path is not a directory.
            PermissionError: If access to target directory is denied.
        """
        path_str = args.get("path", ".")
        if not isinstance(path_str, str):
            raise ValueError("Path must be a string.")

        recursive = args.get("recursive", False)
        if not isinstance(recursive, bool):
            recursive = False

        limit = args.get("limit", DEFAULT_FILE_LIMIT)
        if not isinstance(limit, int) or limit <= 0:
            limit = DEFAULT_FILE_LIMIT

        target_dir = resolve_path(state, path_str)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{target_dir}' is not a directory.")

        # Проверка на root/home директории
        if is_restricted_path(target_dir):
            return ToolExecResult(output="Access denied: Cannot show tree for root or home directory.")

        if recursive:
            tree_data, reached_limit = self._build_tree_recursive(target_dir, limit)
        else:
            tree_data, reached_limit = self._build_tree_single_level(target_dir, limit)

        output = format_tree(tree_data, target_dir.name)
        if reached_limit:
            output += f"\n\n... and more items (limit reached)"
        
        return ToolExecResult(output=output)

    def _search_handler(self, state: FileSystemState, args: ToolCallArguments) -> ToolExecResult:
        """
        Handle the 'search' command for file content searching using hypergrep.
        
        This command performs text-based search across files in the specified directory
        using the hypergrep library (Python wrapper for ripgrep). The search respects
        .gitignore files and provides context around matches.
        
        Key features:
        - Automatic .gitignore detection and respect
        - Context lines before and after matches
        - File pattern filtering (e.g., *.py, *.js)
        - Result size limiting to prevent overwhelming output
        - Hidden file filtering for security
        
        Args:
            state: The current file system session state containing CWD information.
            args: ToolCallArguments containing:
                - path: Target directory path (defaults to current directory)
                - query: Search query string (required)
                - file_pattern: Optional file pattern filter
        
        Returns:
            ToolExecResult containing formatted search results with context.
        
        Raises:
            ValueError: If query is missing or invalid.
            NotADirectoryError: If target path is not a directory.
            PermissionError: If access to target directory is denied.
            ImportError: If hypergrep is not available.
        """
        path_str = args.get("path", ".")
        if not isinstance(path_str, str):
            raise ValueError("Path must be a string.")

        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query is required and must be a non-empty string.")

        file_pattern = args.get("file_pattern")
        if file_pattern is not None and not isinstance(file_pattern, str):
            raise ValueError("File pattern must be a string.")

        target_dir = resolve_path(state, path_str)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{target_dir}' is not a directory.")

        # Проверка на root/home директории
        if is_restricted_path(target_dir):
            return ToolExecResult(output="Access denied: Cannot search in root or home directory.")

        try:
            results = search_files_with_hypergrep(str(target_dir), query, file_pattern, str(state.cwd))
            output = format_search_results(results, str(state.cwd), MAX_SEARCH_RESULTS, MAX_RIPGREP_MB, MAX_BYTE_SIZE)
            return ToolExecResult(output=output)
        except ImportError as e:
            return ToolExecResult(
                error=str(e),
                error_code=-1
            )
        except Exception as e:
            return ToolExecResult(
                error=f"Search error: {str(e)}",
                error_code=-1
            )



    def _list_files_recursive(self, dir_path: pathlib.Path, limit: int) -> tuple[list[dict], bool]:
        """
        List files recursively using breadth-first traversal.
        
        This method implements BFS traversal to ensure files at all directory levels
        are discovered before moving deeper into the tree. This prevents missing
        files that might be deeply nested.
        
        The algorithm uses a deque (double-ended queue) for efficient O(1) operations
        when adding/removing directories from the processing queue.
        
        Args:
            dir_path: The root directory to start traversal from.
            limit: Maximum number of files to return before stopping.
        
        Returns:
            A tuple containing:
                - List of file information dictionaries with metadata
                - Boolean indicating if the limit was reached
        
        Note:
            This method automatically filters out hidden files and common
            development directories using the should_ignore_path utility.
        """
        results = []
        queue = deque([dir_path])
        reached_limit = False

        while queue and len(results) < limit:
            current = queue.popleft()
            
            try:
                for child in sorted(current.iterdir(), key=lambda p: p.name):
                    if len(results) >= limit:
                        reached_limit = True
                        break
                    
                    if self._should_ignore_path(child):
                        continue
                    
                    file_info = get_file_info(child)
                    results.append(file_info)
                    
                    if child.is_dir():
                        queue.append(child)
                        
            except PermissionError:
                continue  # Skip directories we can't access
        
        return results, reached_limit

    def _list_files_single_level(self, dir_path: pathlib.Path, limit: int) -> tuple[list[dict], bool]:
        """
        List files in a single directory level without recursion.
        
        This method provides a fast, single-level listing of files and directories
        in the specified directory. It's useful when you only need to see the
        immediate contents without exploring subdirectories.
        
        Args:
            dir_path: The directory to list contents from.
            limit: Maximum number of files to return before stopping.
        
        Returns:
            A tuple containing:
                - List of file information dictionaries with metadata
                - Boolean indicating if the limit was reached
        
        Note:
            This method automatically filters out hidden files and common
            development directories using the should_ignore_path utility.
        """
        results = []
        reached_limit = False
        
        try:
            for child in sorted(dir_path.iterdir(), key=lambda p: p.name):
                if len(results) >= limit:
                    reached_limit = True
                    break
                
                if self._should_ignore_path(child):
                    continue
                
                file_info = get_file_info(child)
                results.append(file_info)
                
        except PermissionError:
            pass
        
        return results, reached_limit

    def _build_tree_recursive(self, dir_path: pathlib.Path, limit: int) -> tuple[list[dict], bool]:
        """
        Build tree structure recursively using breadth-first traversal.
        
        This method constructs a hierarchical tree representation of the directory
        structure by traversing levels breadth-first. Each tree item contains
        depth information for proper indentation in the final output.
        
        The BFS approach ensures that all items at the same depth are processed
        together, creating a more intuitive tree visualization.
        
        Args:
            dir_path: The root directory to build the tree from.
            limit: Maximum number of tree items to return before stopping.
        
        Returns:
            A tuple containing:
                - List of tree item dictionaries with name, type, depth, and path
                - Boolean indicating if the limit was reached
        
        Note:
            Tree items are sorted alphabetically at each level for consistent output.
        """
        results = []
        queue = deque([(dir_path, 0)])  # (path, depth)
        reached_limit = False

        while queue and len(results) < limit:
            current, depth = queue.popleft()
            
            try:
                for child in sorted(current.iterdir(), key=lambda p: p.name):
                    if len(results) >= limit:
                        reached_limit = True
                        break
                    
                    if self._should_ignore_path(child):
                        continue
                    
                    tree_item = {
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "depth": depth,
                        "path": str(child.relative_to(dir_path))
                    }
                    results.append(tree_item)
                    
                    if child.is_dir():
                        queue.append((child, depth + 1))
                        
            except PermissionError:
                continue
        
        return results, reached_limit

    def _build_tree_single_level(self, dir_path: pathlib.Path, limit: int) -> tuple[list[dict], bool]:
        """
        Build tree structure for single level without recursion.
        
        This method creates a flat tree representation showing only the immediate
        contents of the specified directory. All items have depth 0 since they're
        at the same level.
        
        Args:
            dir_path: The directory to build the tree from.
            limit: Maximum number of tree items to return before stopping.
        
        Returns:
            A tuple containing:
                - List of tree item dictionaries with name, type, and depth 0
                - Boolean indicating if the limit was reached
        
        Note:
            This method is faster than recursive building and useful for
            quick directory overviews.
        """
        results = []
        reached_limit = False
        
        try:
            for child in sorted(dir_path.iterdir(), key=lambda p: p.name):
                if len(results) >= limit:
                    reached_limit = True
                    break
                
                if self._should_ignore_path(child):
                    continue
                
                tree_item = {
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "depth": 0,
                    "path": child.name
                }
                results.append(tree_item)
                
        except PermissionError:
            pass
        
        return results, reached_limit

    def _should_ignore_path(self, path: pathlib.Path) -> bool:
        """
        Check if a path should be ignored based on filtering rules.
        
        This method determines whether a file or directory should be excluded
        from processing based on common development patterns and security
        considerations.
        
        Filtering rules:
        - Hidden files and directories (starting with '.')
        - Common development directories (node_modules, __pycache__, etc.)
        - Build and dependency directories (build, dist, target, etc.)
        
        Args:
            path: The pathlib.Path object to check for filtering.
        
        Returns:
            True if the path should be ignored, False otherwise.
        
        Note:
            This method delegates to the should_ignore_path utility function
            from file_utils to maintain consistency across the codebase.
        """
        # Используем утилиту из file_utils
        from .utils.file_utils import should_ignore_path
        return should_ignore_path(path)
