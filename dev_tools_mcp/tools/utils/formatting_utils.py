import pathlib
from typing import Dict, List


def format_file_list(files: List[Dict]) -> str:
    """Format file list for output - без эмодзи."""
    if not files:
        return "No files found."
    
    lines = []
    for file_info in files:
        prefix = "DIR " if file_info["is_dir"] else "FILE"
        line = f"{prefix:<4} {file_info['name']:<30} {file_info['size']:>10} {file_info['modified']} {file_info['permissions']}"
        lines.append(line)
    
    return "\n".join(lines)


def format_tree(tree_data: List[Dict], root_name: str) -> str:
    """Format tree structure for output - без эмодзи."""
    if not tree_data:
        return f"{root_name}\n└── (empty)"
    
    lines = [root_name]
    
    for item in tree_data:
        indent = "  " * item["depth"]
        prefix = "└── " if item == tree_data[-1] else "├── "
        item_type = "DIR " if item["is_dir"] else "FILE"
        
        lines.append(f"{indent}{prefix}{item_type} {item['name']}")
    
    return "\n".join(lines)





def format_search_results(results: List, cwd: str, max_results: int, max_ripgrep_mb: float, max_byte_size: int) -> str:
    """Format search results with size limits - твой код."""
    grouped = {}
    output = ""

    if len(results) >= max_results:
        output += f"Showing first {max_results} of {max_results}+ results. Use a more specific search.\n\n"
    else:
        output += f"Found {len(results)} result(s).\n\n"

    for r in results:
        rel_path = pathlib.Path(r.file_path).relative_to(cwd)
        grouped.setdefault(str(rel_path), []).append(r)

    byte_size = len(output.encode("utf-8"))
    was_limit = False

    for file_path, file_results in grouped.items():
        file_block = f"{pathlib.PurePosixPath(file_path)}\n|----\n"
        if byte_size + len(file_block.encode("utf-8")) >= max_byte_size:
            was_limit = True
            break

        output += file_block
        byte_size += len(file_block.encode("utf-8"))

        for idx, r in enumerate(file_results):
            all_lines = [*r.before_context, r.match, *r.after_context]
            block = "".join(f"|{line.rstrip()}\n" for line in all_lines)

            if byte_size + len(block.encode("utf-8")) >= max_byte_size:
                was_limit = True
                break

            output += block
            byte_size += len(block.encode("utf-8"))

            if idx < len(file_results) - 1:
                sep = "|----\n"
                if byte_size + len(sep.encode("utf-8")) >= max_byte_size:
                    was_limit = True
                    break
                output += sep
                byte_size += len(sep.encode("utf-8"))

        if was_limit:
            break

        closing = "|----\n\n"
        if byte_size + len(closing.encode("utf-8")) >= max_byte_size:
            was_limit = True
            break
        output += closing
        byte_size += len(closing.encode("utf-8"))

    if was_limit:
        trunc_msg = f"\n[Results truncated due to exceeding {max_ripgrep_mb}MB limit.]"
        if byte_size + len(trunc_msg.encode("utf-8")) < max_byte_size:
            output += trunc_msg

    return output.strip()
