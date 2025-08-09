# MCP Server Design for `coding_tools_mcp`

---

### 1. Introduction

This document outlines the design and architecture of an MCP server that will expose the core functionalities of the `coding_tools_mcp` project as tools for external agents. The objective is to enable other systems to leverage the powerful capabilities of `TraeAgent` for software engineering tasks, such as command execution, code editing, codebase searching, and Git operations.

The analysis of the project, based on `docs/project_breakdown.md`, has revealed that several core tools and features of `TraeAgent` are ideal candidates for exposure via an MCP interface. Tools related to the agent's internal thought process (`sequential_thinking`, `task_done`), as well as observability features (`LakeView`, `TrajectoryRecorder`), will remain internal.

### 2. Server Architecture

The server will be built using the `FastMCP` library, following the pattern demonstrated in `docs/context/server.py`. It will be an asynchronous FastAPI/Starlette application where each exposed tool is implemented as an `async` function wrapped with the `@mcp_app.tool()` decorator.

The server will encapsulate the logic for:
- Initializing the necessary components from `coding_tools_mcp`.
- Invoking the corresponding tool classes (`BashTool`, `TextEditorTool`, etc.).
- Handling input parameters and returning results in a standardized format.

### 3. Exposed Tools

The following tools will be implemented and exposed by the MCP server.

#### 3.1. `bash`

*   **Description**: Provides the ability to execute arbitrary shell commands in a persistent session. This allows an external agent to interact with the operating system, file system, run tests, install dependencies, and perform other system operations.
*   **Based on**: `coding_tools_mcp/tools/bash_tool.py`.
*   **Parameters**:
    *   `command` (string, required): The command to execute.
    *   `restart` (boolean, optional): A flag to restart the bash session.
*   **Returns**: The standard output (`stdout`), standard error (`stderr`), and exit code of the executed command.

#### 3.2. `file_editor`

*   **Description**: A powerful tool for file manipulation. It combines several operations for working with text files and directories.
*   **Based on**: `coding_tools_mcp/tools/edit_tool.py` (internally named `str_replace_based_edit_tool`).
*   **Parameters**:
    *   `operation` (enum, required): The type of operation. Possible values: `view`, `create`, `replace`, `insert`.
    *   `path` (string, required): The absolute path to the file or directory.
    *   `content` (string, optional): The content for a `create` or `insert` operation.
    *   `old_string` (string, optional): The string to search for in a `replace` operation. Must be unique within the file.
    *   `new_string` (string, optional): The replacement string for a `replace` operation.
    *   `line_number` (integer, optional): The line number for an `insert` operation.
*   **Returns**: The result of the operation. For `view`, the content of the file/directory. For `create`, `replace`, `insert`, a success message and a snippet of the changed code for context.

#### 3.3. `json_editor`

*   **Description**: A specialized tool for precise editing of JSON files using JSONPath expressions.
*   **Based on**: `coding_tools_mcp/tools/json_edit_tool.py`.
*   **Parameters**:
    *   `operation` (enum, required): The type of operation: `view`, `set`, `add`, `remove`.
    *   `file_path` (string, required): The absolute path to the JSON file.
    *   `json_path` (string, required): The JSONPath expression to target an element.
    *   `value` (any, optional): The JSON-compatible value for `set` and `add` operations.
*   **Returns**: The result of the operation. For `view`, the requested data. For `set`, `add`, `remove`, a success message.

#### 3.4. `code_search`

*   **Description**: A tool for intelligent codebase searching using the Code Knowledge Graph (CKG). It allows finding definitions of functions, classes, and methods.
*   **Based on**: `coding_tools_mcp/tools/ckg_tool.py`.
*   **Parameters**:
    *   `command` (enum, required): The type of search: `search_function`, `search_class`, `search_class_method`.
    *   `path` (string, required): The absolute path to the root directory of the codebase.
    *   `identifier` (string, required): The name (identifier) of the function, class, or method to search for.
    *   `print_body` (boolean, optional): Whether to include the body of the found element in the result.
*   **Returns**: A list of found matches, including the file path, line number, and optionally, the code body.

#### 3.5. `git_diff`

*   **Description**: A tool to retrieve changes in a Git repository. It can show current uncommitted changes or changes relative to a specific commit.
*   **Based on**: The logic of the `get_git_diff` method from `coding_tools_mcp/agent/trae_agent.py`.
*   **Parameters**:
    *   `base_commit` (string, optional): The commit hash to diff against. If not provided, it will show current uncommitted changes (`git diff HEAD`).
    *   `path` (string, required): The absolute path to the Git repository.
*   **Returns**: A string with the output of the `git diff` command.

#### 3.6. `sequential_thinking`

*   **Description**: A meta-tool that allows an external agent to structure and communicate complex, multi-step reasoning. Instead of performing a direct action, the agent can use this tool to record its thoughts, hypotheses, and plans. This can be useful for debugging or for a human operator to follow the agent's logic.
*   **Based on**: `coding_tools_mcp/tools/sequential_thinking_tool.py`.
*   **Parameters**:
    *   `thought` (string, required): The text of the thought or reasoning step.
    *   `thought_number` (integer, required): The sequential number of the thought in the sequence.
    *   `total_thoughts` (integer, required): The total estimated number of thoughts in the sequence.
    *   ... and other optional parameters for branching and revising thoughts.
*   **Returns**: A message confirming the thought was recorded and the current state of the thought history.

#### 3.7. `task_done`

*   **Description**: A signaling tool that an external agent calls to indicate the full completion of its task. This allows the system managing `TraeAgent` as a service to know when the session can be terminated and results can be summarized.
*   **Based on**: `coding_tools_mcp/tools/task_done_tool.py`.
*   **Parameters**: None.
*   **Returns**: A simple confirmation: "Task done.".

### 4. `trae_agent` Analysis

The analysis of `trae_agent.py` showed that the agent itself possesses a number of awesome but *internal* features that make it effective. The key one is its ability to integrate with MCP servers (`initialise_mcp`, `discover_mcp_tools`). This means `TraeAgent` is designed as an extensible system capable of consuming external tools.

Our task is not to rewrite `TraeAgent`, but to provide its *capabilities* to other agents. Therefore, we are not exposing its internal task management logic or system prompts. Instead, we are taking its "hands"—its tools—and making them available to others.

The `get_git_diff` function is an exception. It's not a formal "tool" but a class method. However, its functionality is so useful and atomic that it should be wrapped into a full-fledged `git_diff` tool on our MCP server.

### 5. Conclusion

The proposed MCP server will transform `coding_tools_mcp` from a monolithic agent into a powerful, reusable backend for software engineering tasks. By exposing key tools (`bash`, `file_editor`, `json_editor`, `code_search`, `git_diff`), we create a service that can be integrated into larger and more complex automation systems, allowing other agents to delegate low-level but critical tasks related to code and environment manipulation.

---
