import pathlib
import json
from typing import Dict, List


def format_file_list(files: List[Dict]) -> str:
    """
    Format file list as structured JSON for LLM consumption.
    
    Returns a JSON string with clear structure that LLMs can easily parse
    and understand, instead of hard-to-parse plain text.
    """
    if not files:
        return "{\n  \"status\": \"empty\",\n  \"message\": \"No files found\",\n  \"files\": []\n}"
    
    # Create structured output
    file_list = []
    for file_info in files:
        file_entry = {
            "name": file_info["name"],
            "type": "directory" if file_info["is_dir"] else "file",
            "size": file_info["size"],
            "modified": file_info["modified"],
            "permissions": file_info["permissions"],
            "path": file_info["path"]
        }
        file_list.append(file_entry)
    
    # Return structured JSON
    return json.dumps({
        "status": "success",
        "count": len(file_list),
        "files": file_list
    }, indent=2)


def format_tree(tree_data: List[Dict], root_name: str) -> str:
    """
    Format tree structure as structured JSON for LLM consumption.
    
    Returns a JSON string with hierarchical structure that LLMs can easily
    parse and understand, instead of hard-to-parse plain text.
    """
    if not tree_data:
        return json.dumps({
            "status": "empty",
            "root": root_name,
            "message": "Directory is empty",
            "tree": []
        }, indent=2)
    
    # Create structured tree output
    tree_items = []
    for item in tree_data:
        tree_entry = {
            "name": item["name"],
            "type": "directory" if item["is_dir"] else "file",
            "depth": item["depth"],
            "path": item["path"]
        }
        tree_items.append(tree_entry)
    
    # Return structured JSON
    return json.dumps({
        "status": "success",
        "root": root_name,
        "count": len(tree_items),
        "tree": tree_items
    }, indent=2)





def format_search_results(results: List, cwd: str, max_results: int, max_ripgrep_mb: float, max_byte_size: int) -> str:
    """
    Format search results as structured JSON for LLM consumption.
    
    Returns a JSON string with organized search results that LLMs can easily
    parse and understand, instead of hard-to-parse plain text.
    """
    if not results:
        return json.dumps({
            "status": "empty",
            "message": "No search results found",
            "results": []
        }, indent=2)
    
    # Group results by file
    grouped = {}
    for r in results:
        rel_path = pathlib.Path(r.file_path).relative_to(cwd)
        grouped.setdefault(str(rel_path), []).append(r)
    
    # Check if we hit limits
    was_limit = len(results) >= max_results
    byte_size = 0
    formatted_results = []
    
    for file_path, file_results in grouped.items():
        if len(formatted_results) >= max_results:
            break
            
        file_result = {
            "file": file_path,
            "matches": []
        }
        
        for r in file_results:
            if len(file_result["matches"]) >= max_results:
                break
                
            match = {
                "line": r.match.strip(),
                "line_number": getattr(r, 'line_number', '?'),
                "context": {
                    "before": [line.strip() for line in r.before_context],
                    "after": [line.strip() for line in r.after_context]
                }
            }
            file_result["matches"].append(match)
            
            # Check byte size limit
            match_bytes = len(json.dumps(match).encode("utf-8"))
            if byte_size + match_bytes >= max_byte_size:
                was_limit = True
                break
            byte_size += match_bytes
        
        formatted_results.append(file_result)
        
        if was_limit:
            break
    
    # Return structured JSON
    return json.dumps({
        "status": "success",
        "total_results": len(results),
        "showing_results": len(formatted_results),
        "was_truncated": was_limit,
        "results": formatted_results
    }, indent=2)
