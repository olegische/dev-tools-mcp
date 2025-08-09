# Project Breakdown: `coding_tools_mcp`

This document provides a detailed technical breakdown of the `coding_tools_mcp` project, analyzing the functionality and purpose of each significant file.

---

## `coding_tools_mcp/cli.py`

This file serves as the command-line interface (CLI) for the Trae Agent, built using the `click` library. It provides the main entry points for interacting with the agent.

**Key functionalities:**

*   **`cli()`**: The main `click` group, acting as the entry point for all commands. It sets the version to "0.1.0".
*   **`run()`**: This command is used to execute a specific task with the Trae Agent.
    *   It accepts a `task` string or a `file_path` to a task description.
    *   Allows overriding LLM `provider`, `model`, `model_base_url`, `api_key`, `max_steps`, and `working_dir`.
    *   Supports a `must_patch` flag for code patching and a `patch_path`.
    *   Configures the agent using `trae_config.yaml` (or `trae_config.json` for backward compatibility) and allows overriding settings via CLI options.
    *   Initializes the `Agent` with the specified `agent_type` (currently only `trae_agent`).
    *   Handles changing the working directory.
    *   Manages console output using `CLIConsole` and `ConsoleFactory`, supporting "simple" or "rich" console types.
    *   Executes the agent's `run` method asynchronously.
    *   Includes error handling for file not found, invalid arguments, and unexpected exceptions, ensuring trajectory is saved even on interruption.
*   **`interactive()`**: This command starts an interactive session with the Trae Agent.
    *   Similar to `run`, it allows configuration overrides.
    *   Creates a `CLIConsole` in `INTERACTIVE` mode.
    *   Dispatches to `_run_simple_interactive_loop` or `_run_rich_interactive_loop` based on the chosen console type.
    *   The simple loop provides basic commands like `help`, `status`, `clear`, and `exit`.
    *   The rich loop leverages a more advanced textual user interface for interaction.
*   **`show_config()`**: Displays the current configuration settings, including general settings and provider-specific details (model, base URL, API key, max tokens, temperature, top_p, top_k for Anthropic). It resolves the config file path with backward compatibility.
*   **`tools()`**: Lists all available tools registered with the agent, along with their descriptions. It imports `tools_registry` from `.tools`.
*   **`resolve_config_file()`**: A helper function to resolve the configuration file path, providing backward compatibility for `.yaml` and `.json` extensions.
*   **`main()`**: The entry point function that calls `cli()`.

This file is crucial for user interaction, allowing users to initiate tasks, configure the agent, and inspect its status and capabilities.

---

## `coding_tools_mcp/agent/agent.py`

This file defines the core `Agent` class, which acts as a high-level orchestrator for different agent types (currently only `TraeAgent`). It handles agent initialization, configuration, trajectory recording, and the overall execution flow of a task. It also manages the CLI console and MCP (Model Context Protocol) integration.

**Key functionalities:**

*   **`AgentType` Enum**: Defines the supported agent types (e.g., `TraeAgent`).
*   **`__init__()`**: Initializes the agent based on the specified `agent_type` and `Config`.
    *   Sets up `TrajectoryRecorder` to log all agent activities. If no trajectory file is provided, it auto-generates one.
    *   Instantiates the specific agent implementation (e.g., `TraeAgent`) and injects the `CLIConsole` and `TrajectoryRecorder`.
    *   Configures Lakeview integration based on the `enable_lakeview` setting in `trae_agent_config`.
*   **`run()`**: The main asynchronous method to execute a task.
    *   Calls `new_task` on the specific agent implementation to set up the task context.
    *   Initializes MCP tools if `allow_mcp_servers` is enabled.
    *   Prints task details to the CLI console.
    *   Executes the agent's `execute_task()` method.
    *   Ensures MCP clients are cleaned up in a `finally` block, even if execution fails.
    *   Handles `KeyboardInterrupt` and other exceptions, ensuring partial trajectory is saved.

This file serves as the central control point for agent operations, abstracting the specifics of different agent implementations and providing a unified execution pipeline.

---

## `coding_tools_mcp/agent/agent_basics.py`

This file defines fundamental data structures and enums used to represent the state and execution of an agent. It's essentially the schema for tracking an agent's progress and results.

**Key data structures:**

*   **`AgentStepState` Enum**: Defines the possible states of a single agent step (e.g., `THINKING`, `CALLING_TOOL`, `REFLECTING`, `COMPLETED`, `ERROR`).
*   **`AgentState` Enum**: Defines the overall state of the agent (e.g., `IDLE`, `RUNNING`, `COMPLETED`, `ERROR`).
*   **`AgentStep` Dataclass**: Represents a single step in an agent's execution. It captures:
    *   `step_number`: The sequential number of the step.
    *   `state`: The current `AgentStepState`.
    *   `thought`: The agent's internal thought process.
    *   `tool_calls`: A list of `ToolCall` objects made in this step.
    *   `tool_results`: A list of `ToolResult` objects from tool executions.
    *   `llm_response`: The `LLMResponse` received from the LLM.
    *   `reflection`: The agent's reflection on the tool results.
    *   `error`: Any error encountered during the step.
    *   `llm_usage`: Token usage for the LLM interaction in this step.
*   **`AgentExecution` Dataclass**: Encapsulates the entire execution of an agent task. It contains:
    *   `task`: The original task description.
    *   `steps`: A list of all `AgentStep` objects.
    *   `final_result`: The final outcome or result of the task.
    *   `success`: A boolean indicating if the task was completed successfully.
    *   `total_tokens`: Aggregated `LLMUsage` for the entire execution.
    *   `execution_time`: Total time taken for execution.
    *   `agent_state`: The overall `AgentState`.
*   **`AgentError` Exception**: A custom exception class for agent-related errors.

This file provides the standardized vocabulary and structure for logging, monitoring, and analyzing the agent's behavior and performance.

---

## `coding_tools_mcp/agent/base_agent.py`

This file defines the abstract `BaseAgent` class, which serves as the foundational blueprint for all LLM-based agents within the system. It establishes the core contract and shared logic for how agents interact with LLMs, execute tools, record their trajectory, and manage their state.

**Key functionalities:**

*   **`__init__()`**: Initializes the base agent with:
    *   An `LLMClient` configured with `ModelConfig`.
    *   A list of `Tool` instances based on the `agent_config`.
    *   A `ToolExecutor` to manage tool execution.
    *   Optional `CLIConsole` and `TrajectoryRecorder` instances.
    *   Clears older CKG databases upon initialization.
*   **Properties**: Provides properties for accessing `llm_client`, `trajectory_recorder`, `cli_console`, `tools`, `task`, `initial_messages`, `model_config`, and `max_steps`.
*   **`set_trajectory_recorder()`**: Sets the trajectory recorder for both the agent and its `LLMClient`.
*   **`set_cli_console()`**: Sets the CLI console for the agent.
*   **`new_task()` (abstract method)**: An abstract method that must be implemented by subclasses to set up a new task, including initial messages and tool configurations.
*   **`execute_task()`**: The main asynchronous method that drives the agent's execution loop.
    *   Iterates through steps up to `_max_steps`.
    *   Calls `_run_llm_step` to get LLM responses and handle tool calls.
    *   Updates `AgentStep` and `AgentExecution` objects.
    *   Handles exceptions during execution, updating the agent state to `ERROR`.
    *   Finalizes trajectory recording and cleans up MCP clients.
*   **`_run_llm_step()`**: Manages a single LLM interaction step:
    *   Sets the step state to `THINKING`.
    *   Calls `llm_client.chat()` to get the LLM response.
    *   Updates token usage.
    *   Checks if the LLM indicates task completion; if so, sets `AgentState.COMPLETED`.
    *   If tool calls are present, dispatches to `_tool_call_handler`.
*   **`reflect_on_result()`**: A method for the agent to reflect on tool execution results (can be overridden by subclasses).
*   **`llm_indicates_task_completed()`**: Checks if the LLM's response indicates task completion (can be overridden).
*   **`_is_task_completed()`**: Determines if the task is truly completed (can be overridden).
*   **`task_incomplete_message()`**: Provides a message for incomplete tasks (can be overridden).
*   **`cleanup_mcp_clients()` (abstract method)**: An abstract method for subclasses to implement MCP client cleanup.
*   **`_update_cli_console()`**: Updates the CLI console with current step and execution status.
*   **`_update_llm_usage()`**: Aggregates LLM token usage.
*   **`_record_handler()`**: Records agent steps to the `TrajectoryRecorder`.
*   **`_tool_call_handler()`**: Executes tool calls (either parallel or sequential based on `_model_config.parallel_tool_calls`) and processes their results, potentially triggering reflection.

This file is the core architectural component, defining the fundamental lifecycle and interaction patterns for any agent built on this framework.

---

## `coding_tools_mcp/agent/trae_agent.py`

This file defines `TraeAgent`, a specialized agent for software engineering tasks, inheriting from `BaseAgent`. It customizes the general agent behavior to handle project-specific context, git operations, and crucially, the integration of MCP (Model Context Protocol) servers and their tools.

**Key functionalities:**

*   **`TraeAgentToolNames`**: A list of default tool names used by `TraeAgent`.
*   **`__init__()`**: Initializes `TraeAgent` with `TraeAgentConfig`.
    *   Sets up properties for `project_path`, `base_commit`, `must_patch`, `patch_path`.
    *   Configures MCP server details (`mcp_servers_config`, `allow_mcp_servers`) and initializes lists for `mcp_tools` and `mcp_clients`.
    *   Calls the `BaseAgent` constructor.
*   **`initialise_mcp()`**: Asynchronously discovers and initializes MCP tools from configured servers, adding them to the agent's available tools.
*   **`discover_mcp_tools()`**: Iterates through `mcp_servers_config` and `allow_mcp_servers` to connect to MCP servers using `MCPClient`, discovers their tools, and appends them to `self._tools`. Includes error handling and cleanup for failed connections.
*   **`new_task()` (override)**: Overrides the base method to set up a new software engineering task.
    *   Sets the `_task` and initializes default tools if none are provided.
    *   Constructs the initial user message, including `[Project root path]` and `[Problem statement]`.
    *   Extracts optional arguments like `base_commit`, `must_patch`, and `patch_path`.
    *   Starts trajectory recording.
*   **`execute_task()` (override)**: Overrides the base method to finalize trajectory recording after task execution and, if `patch_path` is provided, writes the git diff to that file.
*   **`get_system_prompt()`**: Returns `TRAE_AGENT_SYSTEM_PROMPT` from `agent_prompt.py`, which provides the specific instructions for software engineering tasks.
*   **`reflect_on_result()` (override)**: Overrides the base method to disable reflection for `TraeAgent` (returns `None`).
*   **`get_git_diff()`**: Executes `git diff` commands to get the changes in the project, either from the current state or relative to a `base_commit`.
*   **`remove_patches_to_tests()`**: A utility function (adapted from Aider-AI) to filter out changes to test directories from a given patch string, ensuring that the agent's generated patches don't interfere with acceptance testing.
*   **`llm_indicates_task_completed()` (override)**: Overrides the base method to specifically check if the LLM's response includes a call to the `task_done` tool, indicating completion.
*   **`_is_task_completed()` (override)**: Enhances task completion detection. If `must_patch` is "true", it checks if a non-empty patch (excluding test changes) has been generated.
*   **`task_incomplete_message()` (override)**: Provides a specific error message if the patch is empty when `must_patch` is true.
*   **`cleanup_mcp_clients()` (override)**: Cleans up all connected MCP clients to prevent resource leaks.

This file is the core intelligence for solving software engineering problems, integrating domain-specific logic and tools into the general agent framework.

---

## `coding_tools_mcp/agent/__init__.py`

This `__init__.py` file simply exposes the main agent classes (`Agent`, `BaseAgent`, `TraeAgent`) from the `agent` module, making them easily importable from the `coding_tools_mcp.agent` package. It's a standard Python package initialization file.

---

## `coding_tools_mcp/prompt/agent_prompt.py`

This file contains `TRAE_AGENT_SYSTEM_PROMPT`, a critical piece of the agent's intelligence. It's the system-level instruction set that guides the `TraeAgent`'s behavior, outlining its primary goal (resolving GitHub issues), a methodical step-by-step process, and crucial rules for tool usage.

**Key contents:**

*   **`TRAE_AGENT_SYSTEM_PROMPT`**: A multi-line string containing detailed instructions for the agent.
    *   **File Path Rule**: Emphasizes the requirement for absolute paths for file-related tools, combining `[Project root path]` with relative paths.
    *   **Primary Goal**: Resolving GitHub issues through code exploration, bug reproduction, diagnosis, fix implementation, and rigorous testing.
    *   **Methodical Steps**: A numbered list outlining the expected workflow:
        1.  Understand the Problem
        2.  Explore and Locate
        3.  Reproduce the Bug (Crucial Step: requires creating a reproduction script/test case)
        4.  Debug and Diagnose
        5.  Develop and Implement a Fix
        6.  Verify and Test Rigorously (requires verifying fix, preventing regressions, writing new tests, considering edge cases)
        7.  Summarize Your Work
    *   **Guiding Principle**: Act like a "senior software engineer," prioritizing correctness, safety, and test-driven development.
    *   **Guide for `sequential_thinking` tool**: Provides detailed instructions on how to use the `sequential_thinking` tool effectively, including adjusting `total_thoughts`, revising previous thoughts, branching, expressing uncertainty, and generating/verifying hypotheses.
    *   **`task_done` tool usage**: Specifies that `task_done` should only be called after verification.

This prompt is the fundamental programming that dictates the `TraeAgent`'s strategic approach and operational guidelines, ensuring it follows a structured and robust problem-solving methodology.

---

## `coding_tools_mcp/prompt/__init__.py`

This `__init__.py` file is empty except for the license header. It serves no functional purpose other than marking `prompt` as a Python package, allowing its contents (like `agent_prompt.py`) to be imported.

---

## `coding_tools_mcp/tools/base.py`

This file defines the foundational abstract classes and data structures for all tools used by the agent. It establishes the `Tool` interface, requiring methods for `name`, `description`, `parameters`, and `execute`. It also defines `ToolCall` and `ToolResult` for representing tool interactions and their outcomes. Crucially, it includes `ToolExecutor`, which handles both parallel and sequential execution of tool calls.

**Key components:**

*   **`ToolError` Exception**: A custom exception for tool-related errors.
*   **`ToolExecResult` Dataclass**: Represents the raw output and error code from a tool's execution.
*   **`ToolResult` Dataclass**: Represents the structured result of a tool execution, including `call_id`, `name`, `success` status, `result` content, and `error` message.
*   **`ToolCall` Dataclass**: Represents a parsed instruction to call a tool, including its `name`, `call_id`, and `arguments`.
*   **`ToolParameter` Dataclass**: Defines the schema for a tool's input parameters, including `name`, `type`, `description`, `enum` (for allowed values), `items` (for array types), and `required` status.
*   **`Tool` (Abstract Base Class)**: The core interface for all tools. Subclasses must implement:
    *   `get_name()`: Returns the tool's unique name.
    *   `get_description()`: Returns a human-readable description of the tool.
    *   `get_parameters()`: Returns a list of `ToolParameter` objects defining the tool's input schema.
    *   `execute()`: An asynchronous method that performs the tool's action with given arguments and returns a `ToolExecResult`.
    *   `json_definition()`: Generates a JSON schema representation of the tool, used for LLM tool calling.
    *   `get_input_schema()`: Generates the OpenAPI-compatible input schema for the tool, with special handling for OpenAI's strict parameter requirements.
*   **`ToolExecutor` Class**: Manages the execution of tool calls.
    *   `execute_tool_call()`: Executes a single `ToolCall`, handling tool lookup, error handling, and wrapping the result in a `ToolResult`.
    *   `parallel_tool_call()`: Executes multiple `ToolCall` objects concurrently using `asyncio.gather`.
    *   `sequential_tool_call()`: Executes multiple `ToolCall` objects one after another.

This file provides the fundamental framework for defining, describing, and executing all tools within the agent's ecosystem, ensuring a standardized and extensible approach to agent capabilities.

---

## `coding_tools_mcp/tools/bash_tool.py`

This file implements the `BashTool`, which allows the agent to execute arbitrary bash commands within a persistent shell session. It is a critical tool for the agent's ability to interact with the file system, run tests, and perform general system operations.

**Key components:**

*   **`_BashSession` Class**: A private helper class that manages a single, persistent bash shell process.
    *   Handles starting and stopping the shell.
    *   Provides a `run()` method to execute commands, capture stdout/stderr, and retrieve the exit code.
    *   Implements a sentinel-based mechanism to reliably extract command output and error codes, even with asynchronous I/O.
    *   Includes timeout logic to prevent commands from hanging indefinitely.
    *   Handles Windows compatibility for shell commands.
*   **`BashTool` Class**: Inherits from `Tool`.
    *   **`get_name()`**: Returns "bash".
    *   **`get_description()`**: Provides a detailed description of the tool's capabilities, including persistence, access to common packages, and advice on avoiding large outputs or running long-lived commands in the background.
    *   **`get_parameters()`**: Defines the `command` (string, required) and `restart` (boolean, optional) parameters. The `restart` parameter allows the agent to reset the bash session.
    *   **`execute()`**: Implements the tool's logic:
        *   If `restart` is true, it stops and restarts the internal `_BashSession`.
        *   If no session exists, it starts a new one.
        *   Executes the provided `command` using the `_BashSession.run()` method.
        *   Returns a `ToolExecResult` with the command's output, error, and exit code.

This tool is essential for the agent's operational capabilities, enabling it to perform low-level system interactions necessary for software development tasks.

---

## `coding_tools_mcp/tools/ckg_tool.py`

This file defines the `CKGTool` (Code Knowledge Graph Tool), which allows the agent to query a codebase for functions, classes, and class methods. It builds and maintains a `CKGDatabase` for each codebase path, enabling structured searches for code definitions.

**Key functionalities:**

*   **`CKGToolCommands`**: A list of supported commands: `search_function`, `search_class`, `search_class_method`.
*   **`__init__()`**: Initializes the tool and maintains a dictionary `_ckg_databases` to store `CKGDatabase` instances, keyed by codebase path, to reuse existing databases.
*   **`get_name()`**: Returns "ckg".
*   **`get_description()`**: Provides a description of the tool, its commands, output truncation behavior, and a note about CKG accuracy.
*   **`get_parameters()`**: Defines parameters: `command` (enum of `CKGToolCommands`), `path` (absolute path to codebase), `identifier` (name of function/class to search), and `print_body` (boolean, optional, to include code body in results).
*   **`execute()`**: The main execution logic:
    *   Validates input parameters (`command`, `path`, `identifier`).
    *   Ensures the provided `path` is an existing directory.
    *   Retrieves or creates a `CKGDatabase` instance for the given codebase path.
    *   Dispatches to internal helper methods (`_search_function`, `_search_class`, `_search_class_method`) based on the `command`.
    *   Returns a `ToolExecResult` with the search results or an error.
*   **`_search_function()`**: Queries the `CKGDatabase` for function entries matching the `identifier`. Formats the output with file paths, line numbers, and optionally the function body, truncating if too long.
*   **`_search_class()`**: Queries the `CKGDatabase` for class entries. Formats output with file paths, line numbers, and optionally class fields, methods, and body.
*   **`_search_class_method()`**: Queries the `CKGDatabase` for class method entries. Formats output similarly to `_search_function`, including the parent class.

This tool is vital for the agent's code understanding capabilities, allowing it to quickly locate and inspect specific code constructs without needing to manually read entire files or directories.

---

## `coding_tools_mcp/tools/edit_tool.py`

This file defines the `TextEditorTool` (named `str_replace_based_edit_tool`), a crucial instrument for the agent to modify files. It supports `view` (to inspect files or directories), `create` (to make new files), `str_replace` (for precise string-based replacements), and `insert` (to add content at a specific line).

**Key functionalities:**

*   **`EditToolSubCommands`**: A list of supported sub-commands: `view`, `create`, `str_replace`, `insert`.
*   **`SNIPPET_LINES`**: Defines the number of lines to show around an edit for context.
*   **`get_name()`**: Returns "str_replace_based_edit_tool".
*   **`get_description()`**: Provides a detailed description of the tool's capabilities, including how `view` works for files and directories, the constraint on `create` (cannot overwrite existing files), output truncation, and specific, crucial notes for `str_replace` (exact match, uniqueness, whitespace sensitivity).
*   **`get_parameters()`**: Defines parameters for each command, including `command`, `file_text` (for `create`), `insert_line` (for `insert`), `new_str` (for `str_replace` and `insert`), `old_str` (for `str_replace`), `path` (absolute path to file/directory), and `view_range` (for `view` on files).
*   **`execute()`**: The main execution logic, dispatching to specific handlers based on the `command`. Includes robust path validation (absolute path, existence checks, directory vs. file constraints).
*   **`_view_handler()` and `_view()`**: Implements the `view` command. For files, it reads content and optionally applies line range filtering, then formats it with line numbers. For directories, it lists contents up to 2 levels deep using `find`.
*   **`_create_handler()`**: Implements the `create` command, writing `file_text` to the specified `path`.
*   **`str_replace()`**: Implements the `str_replace` command. It reads the file, checks for unique occurrences of `old_str` (case-sensitive, whitespace-sensitive), performs the replacement, writes the new content, and returns a snippet of the changed area. Raises `ToolError` if `old_str` is not found or is not unique.
*   **`_insert()`**: Implements the `insert` command, inserting `new_str` after `insert_line`. Handles line number validation and returns a snippet.
*   **`read_file()` and `write_file()`**: Helper methods for file I/O, with error handling.
*   **`_make_output()`**: Formats file content for display, adding line numbers and handling truncation.

This tool is the agent's primary means of directly manipulating the codebase, enabling it to implement fixes, create new files, and inspect code with precision. Its strict requirements for `str_replace` highlight the need for careful agent reasoning.

---

## `coding_tools_mcp/tools/json_edit_tool.py`

This file implements the `JSONEditTool`, a specialized tool for precise modifications of JSON files using JSONPath expressions. It supports `view`, `set`, `add`, and `remove` operations, allowing the agent to interact with structured data.

**Key functionalities:**

*   **`get_name()`**: Returns "json_edit_tool".
*   **`get_description()`**: Provides a detailed description of the tool, its supported operations (`view`, `set`, `add`, `remove`), and examples of JSONPath syntax. It emphasizes safe parsing and formatting preservation.
*   **`get_parameters()`**: Defines parameters: `operation` (enum of supported operations), `file_path` (absolute path to JSON file), `json_path` (JSONPath expression, optional for `view`), `value` (JSON-serializable value for `set`/`add`), and `pretty_print` (boolean, optional, for formatted output).
*   **`execute()`**: The main execution logic, validating parameters and dispatching to specific asynchronous handlers based on the `operation`. Ensures `file_path` is absolute.
*   **`_load_json_file()`**: Loads and parses a JSON file, raising `ToolError` on file not found, empty file, or invalid JSON.
*   **`_save_json_file()`**: Saves JSON data to a file, with optional pretty-printing.
*   **`_parse_jsonpath()`**: Parses a JSONPath expression using `jsonpath_ng`, with error handling for invalid expressions.
*   **`_view_json()`**: Implements the `view` operation. If `json_path_str` is provided, it finds and displays matches; otherwise, it displays the entire JSON content.
*   **`_set_json_value()`**: Implements the `set` operation, updating values at specified JSONPaths.
*   **`_add_json_value()`**: Implements the `add` operation, adding new key-value pairs to objects or appending to arrays at specified JSONPaths.
*   **`_remove_json_value()`**: Implements the `remove` operation, deleting elements at specified JSONPaths.

This tool is crucial for managing configuration files, API responses, or any other JSON-formatted data within a project, providing a powerful and precise way for the agent to interact with structured data.

---

## `coding_tools_mcp/tools/mcp_tool.py`

This file defines the `MCPTool` class, which acts as a wrapper for tools provided by external MCP (Model Context Protocol) servers. It dynamically generates its name, description, and parameters based on the `mcp.types.Tool` object it encapsulates. This allows the agent to seamlessly integrate and utilize capabilities from various connected MCP servers, extending its functionality beyond its built-in tools.

**Key functionalities:**

*   **`__init__()`**: Initializes the `MCPTool` with an `mcp.ClientSession` (`client`) and an `mcp.types.Tool` object (`tool`).
*   **`get_name()` (override)**: Returns the name of the wrapped MCP tool.
*   **`get_description()` (override)**: Returns the description of the wrapped MCP tool.
*   **`get_parameters()` (override)**: Dynamically generates the `ToolParameter` list based on the `inputSchema` of the wrapped `mcp.types.Tool`. It handles required parameters and ensures compatibility with different model providers (e.g., OpenAI's strict `required` parameter handling).
*   **`execute()` (override)**: Calls the `client.call_tool()` method with the tool's name and arguments. It then processes the `mcp.types.ToolOutput` to return a `ToolExecResult`, handling both successful outputs and errors from the MCP server.

This tool is a fundamental enabler for the agent's extensibility, allowing it to tap into a potentially vast ecosystem of external services and specialized functionalities provided by MCP servers.

---

## `coding_tools_mcp/tools/run.py`

This file provides a utility function `run` for executing shell commands asynchronously with a timeout. It also includes `maybe_truncate` to prevent excessively long outputs from overwhelming the context window, appending a `TRUNCATED_MESSAGE` when content is clipped.

**Key functionalities:**

*   **`TRUNCATED_MESSAGE`**: A constant string appended to truncated outputs, informing the user that the response was clipped and suggesting `grep -n` for more details.
*   **`MAX_RESPONSE_LEN`**: Defines the maximum length of a response before truncation.
*   **`maybe_truncate()`**: A helper function that truncates a given `content` string if it exceeds `truncate_after` length, appending `TRUNCATED_MESSAGE`.
*   **`run()`**: An asynchronous function to execute a shell `cmd`.
    *   Uses `asyncio.create_subprocess_shell` to run the command in a separate process.
    *   Captures `stdout` and `stderr`.
    *   Applies a `timeout` to prevent long-running commands from blocking.
    *   Uses `asyncio.wait_for` to manage the timeout.
    *   Decodes stdout/stderr and applies `maybe_truncate` to their output.
    *   Returns a tuple: `(returncode, stdout, stderr)`.
    *   Handles `asyncio.TimeoutError` by killing the process and raising a `TimeoutError`.

This file is a low-level but essential utility for any tool that needs to execute external commands, ensuring robustness, preventing indefinite hangs, and managing the size of command outputs to fit within LLM context windows.

---

## `coding_tools_mcp/tools/sequential_thinking_tool.py`

This file defines the `SequentialThinkingTool`, a meta-tool designed to guide the agent's internal thought process. It allows the agent to break down complex problems into sequential steps, revise previous thoughts, branch into alternative approaches, and track its reasoning.

**Key components:**

*   **`ThoughtData` Dataclass**: Represents a single thought step, capturing:
    *   `thought`: The actual text of the thought.
    *   `thought_number`: Current step in the thought sequence.
    *   `total_thoughts`: Estimated total number of thoughts.
    *   `next_thought_needed`: Boolean indicating if more thoughts are required.
    *   `is_revision`, `revises_thought`, `branch_from_thought`, `branch_id`, `needs_more_thoughts`: Optional fields for advanced thought flow control (revisions, branching).
*   **`SequentialThinkingTool` Class**: Inherits from `Tool`.
    *   **`get_name()`**: Returns "sequentialthinking".
    *   **`get_description()`**: Provides an extensive description of the tool's purpose (dynamic and reflective problem-solving), when to use it (complex problems, planning, analysis, multi-step solutions), its key features (adjusting total thoughts, revisions, branching, uncertainty), and detailed explanations of its parameters. It also outlines a recommended thought process (hypothesis generation/verification).
    *   **`get_parameters()`**: Defines all parameters for `ThoughtData` as tool parameters.
    *   **`__init__()`**: Initializes `thought_history` (a list of `ThoughtData` objects) and `branches` (a dictionary to track branched thought sequences).
    *   **`_validate_thought_data()`**: Validates the input arguments against the `ThoughtData` schema, ensuring correct types and logical constraints (e.g., `thought_number` >= 1).
    *   **`_format_thought()`**: Formats a `ThoughtData` object for display, adding visual styling for revisions and branches. (Note: This method is commented out in the `execute` method, suggesting it might be for internal logging or a different console type).
    *   **`execute()`**: The main execution logic:
        *   Validates the input `arguments` into a `ThoughtData` object.
        *   Adjusts `total_thoughts` if `thought_number` exceeds it.
        *   Appends the validated thought to `thought_history`.
        *   Handles branching logic, adding thoughts to specific `branches` if `branch_from_thought` and `branch_id` are provided.
        *   Returns a `ToolExecResult` with a status message and JSON-formatted response data (thought numbers, branches, history length).

This tool is crucial for enabling the agent to perform complex, multi-step reasoning, allowing it to plan, analyze, and adapt its approach in a structured manner, moving beyond simple one-shot responses.

---

## `coding_tools_mcp/tools/task_done_tool.py`

This file defines the `TaskDoneTool`, a simple yet critical tool that signals the completion of a task. Its primary purpose is to inform the agent that it has finished its work, but it comes with a crucial caveat: it should only be called *after* verification and testing have been performed.

**Key functionalities:**

*   **`get_name()`**: Returns "task_done".
*   **`get_description()`**: Provides a concise description, explicitly stating that the tool cannot be called before verification and suggesting the use of reproduction/test scripts.
*   **`get_parameters()`**: Returns an empty list, as this tool takes no arguments.
*   **`execute()`**: Simply returns a `ToolExecResult` with the output "Task done.".

This tool acts as a final checkpoint for the agent, enforcing the principle of verified completion before declaring success.

---

## `coding_tools_mcp/tools/__init__.py`

This `__init__.py` file is crucial for the `tools` module. It imports and exposes all the core tool classes and, most importantly, defines `tools_registry`. This dictionary maps tool names to their respective class implementations, allowing the agent to dynamically instantiate and use tools based on its needs.

**Key functionalities:**

*   **Imports**: Imports `Tool`, `ToolCall`, `ToolExecutor`, `ToolResult` from `base.py`, and all specific tool implementations (`BashTool`, `TextEditorTool`, `JSONEditTool`, `SequentialThinkingTool`, `TaskDoneTool`, `CKGTool`).
*   **`__all__`**: Defines the public API of the `tools` package, listing all classes that should be importable directly.
*   **`tools_registry`**: A dictionary mapping string names (e.g., "bash", "str_replace_based_edit_tool") to their corresponding `Tool` class types. This registry is used by the `BaseAgent` to instantiate the tools it needs.

This file serves as the central configuration and entry point for all built-in tools, making them discoverable and usable by the agent framework.

---

## `coding_tools_mcp/tools/ckg/base.py`

This file defines the fundamental data structures for the Code Knowledge Graph (CKG), specifically `FunctionEntry` and `ClassEntry` dataclasses. These dataclasses are used to store parsed information about functions and classes, including their names, file paths, code bodies, and line numbers. It also provides `extension_to_language`, a mapping crucial for `tree-sitter` to correctly parse different programming languages.

**Key components:**

*   **`FunctionEntry` Dataclass**: Represents a parsed function or method, including:
    *   `name`: Name of the function/method.
    *   `file_path`: Absolute path to the file.
    *   `body`: The full code of the function/method.
    *   `start_line`, `end_line`: Line numbers where the function/method starts and ends.
    *   `parent_function`, `parent_class`: Optional fields to indicate nesting within other functions or classes.
*   **`ClassEntry` Dataclass**: Represents a parsed class, including:
    *   `name`: Name of the class.
    *   `file_path`: Absolute path to the file.
    *   `body`: The full code of the class.
    *   `start_line`, `end_line`: Line numbers where the class starts and ends.
    *   `fields`: String representation of class fields.
    *   `methods`: String representation of class methods.
*   **`extension_to_language` Dictionary**: A mapping from common file extensions (e.g., `.py`, `.java`, `.ts`) to their corresponding `tree-sitter` language names (e.g., "python", "java", "typescript"). This is essential for the `CKGDatabase` to select the correct parser for each source file.

This file provides the schema and basic linguistic mapping necessary for building and querying the code knowledge graph, forming the structural foundation for code understanding.

---

## `coding_tools_mcp/tools/ckg/ckg_database.py`

This file is the backbone of the Code Knowledge Graph (CKG) functionality. it defines the `CKGDatabase` class, which is responsible for parsing codebases, storing code definitions in an SQLite database, and providing query capabilities. It leverages `tree-sitter` for AST parsing and includes mechanisms for database persistence and cleanup.

**Key components and functionalities:**

*   **Constants**: Defines paths (`CKG_DATABASE_PATH`, `CKG_STORAGE_INFO_FILE`) and `CKG_DATABASE_EXPIRY_TIME` for managing CKG storage.
*   **Utility Functions**:
    *   `get_ckg_database_path()`: Generates the database file path based on a codebase hash.
    *   `is_git_repository()`: Checks if a folder is a Git repository.
    *   `get_git_status_hash()`: Generates a hash for Git repositories, considering both commit hash and uncommitted changes.
    *   `get_file_metadata_hash()`: Generates a hash for non-Git repositories based on file metadata (name, modification time, size).
    *   `get_folder_snapshot_hash()`: Determines the appropriate hashing strategy (Git or file metadata) for a given folder.
    *   `clear_older_ckg()`: Deletes CKG databases older than the expiry time.
*   **`SQL_LIST`**: A dictionary containing SQL `CREATE TABLE` statements for `functions` and `classes` tables.
*   **`CKGDatabase` Class**:
    *   **`__init__()`**: Initializes the database connection.
        *   Checks for existing CKG databases based on `codebase_path` and its snapshot hash.
        *   If the snapshot hash matches, it reuses the existing database; otherwise, it creates a new one and deletes the old one.
        *   Initializes the SQLite tables if a new database is created.
        *   Calls `_construct_ckg()` to build the CKG if a new database is created.
    *   **`__del__()`**: Closes the database connection when the object is destroyed.
    *   **`update()`**: Triggers a rebuild of the CKG.
    *   **`_recursive_visit_python()`, `_recursive_visit_java()`, `_recursive_visit_cpp()`, `_recursive_visit_c()`, `_recursive_visit_typescript()`, `_recursive_visit_javascript()`**: A set of recursive methods that traverse the Abstract Syntax Tree (AST) for different programming languages (using `tree-sitter`). These methods extract function and class definitions, including their names, bodies, line numbers, and parent relationships, and insert them into the database.
    *   **`_construct_ckg()`**: The main method for building the CKG. It iterates through all files in the codebase, determines their language based on `extension_to_language`, gets the appropriate `tree-sitter` parser, and then calls the relevant `_recursive_visit_` method to populate the database.
    *   **`_insert_entry()`**: Dispatches to `_insert_function()` or `_insert_class()` based on the entry type.
    *   **`_insert_function()`**: Inserts a `FunctionEntry` into the `functions` table.
    *   **`_insert_class()`**: Inserts a `ClassEntry` into the `classes` table.
    *   **`query_function()`**: Searches the `functions` table for entries matching an `identifier`, optionally filtering by `entry_type` (function or class method).
    *   **`query_class()`**: Searches the `classes` table for entries matching an `identifier`.

This file is a complex piece of engineering that enables the `CKGTool` to provide intelligent, structured insights into the codebase, allowing the agent to understand code structure and relationships without brute-force file reading.

---

## `coding_tools_mcp/utils/config.py`

This file is the central configuration management system for the entire agent. It defines a hierarchy of dataclasses to meticulously structure all configurable parameters, from LLM providers and models to agent-specific settings and MCP server details. It handles loading configurations from YAML files, resolving values from CLI arguments and environment variables, and ensuring backward compatibility with older JSON formats.

**Key components and functionalities:**

*   **`ConfigError` Exception**: A custom exception for configuration-related errors.
*   **`ModelProvider` Dataclass**: Defines configuration for an LLM provider (API key, provider name, base URL, API version).
*   **`ModelConfig` Dataclass**: Defines configuration for a specific LLM model (model name, associated `ModelProvider`, `max_tokens`, `temperature`, `top_p`, `top_k`, `parallel_tool_calls`, `max_retries`, `supports_tool_calling`, etc.).
    *   Includes a `resolve_config_values()` method to override settings based on CLI/environment variables.
*   **`MCPServerConfig` Dataclass**: Defines configuration for an MCP server, including various transport mechanisms (command for stdio, URL for sse/http/websocket) and common properties (timeout, trust, description).
*   **`AgentConfig` Dataclass**: Base class for agent configurations, including `allow_mcp_servers`, `mcp_servers_config`, `max_steps`, `model`, and `tools`.
*   **`TraeAgentConfig` Dataclass**: Specific configuration for the `TraeAgent`, inheriting from `AgentConfig`, with additional settings like `enable_lakeview` and default tools.
    *   Includes a `resolve_config_values()` method for `max_steps`.
*   **`LakeviewConfig` Dataclass**: Configuration for the Lakeview feature, primarily linking to a `ModelConfig` for its own LLM.
*   **`Config` Dataclass**: The top-level configuration container.
    *   **`create()` Class Method**: The primary entry point for loading configurations.
        *   Loads from a YAML `config_file` or `config_string`.
        *   If the `config_file` is JSON, it delegates to `create_from_legacy_config()`.
        *   Parses `model_providers`, `models`, `lakeview`, `mcp_servers`, and `agents` sections, populating the respective dataclasses.
        *   Performs validation, ensuring models link to existing providers and Lakeview is configured if enabled.
    *   **`resolve_config_values()`**: Resolves configuration values across the entire `Config` object, applying overrides from CLI arguments and environment variables to `TraeAgentConfig` and its nested `ModelConfig`.
    *   **`create_from_legacy_config()` Class Method**: Handles conversion from the older JSON-based `LegacyConfig` format to the new `Config` structure.
*   **`resolve_config_value()` Function**: A helper function to determine the final configuration value based on a priority order: CLI > Environment Variable > Config File > Default.

This file is absolutely critical for the agent's operation, as it dictates how the agent is configured, what LLMs it uses, what tools are available, and how it interacts with external MCP services. It provides a robust and flexible system for managing complex configurations.

---

## `coding_tools_mcp/utils/constants.py`

This file is a simple utility that defines a single, crucial constant: `LOCAL_STORAGE_PATH`.

**Key content:**

*   **`LOCAL_STORAGE_PATH`**: A `Path` object pointing to `~/.trae-agent`. This directory is used by the agent to store local data, such as Code Knowledge Graph (CKG) databases and trajectory files.

This file ensures a consistent and predictable location for the agent's persistent local data.

---

## `coding_tools_mcp/utils/lake_view.py`

This file implements the `LakeView` functionality, which is designed to provide high-level, human-readable summaries and tags for agent execution steps. It uses a separate LLM to analyze the agent's trajectory and extract concise task descriptions and categorize steps with predefined tags.

**Key components and functionalities:**

*   **`EXTRACTOR_PROMPT`**: A detailed prompt used to instruct an LLM to extract a concise task description (`<task>`) and bug-specific details (`<details>`) from an agent's step.
*   **`TAGGER_PROMPT`**: A prompt used to instruct an LLM to categorize an agent's step with predefined tags (e.g., `WRITE_TEST`, `EXAMINE_CODE`, `WRITE_FIX`, `THINK`).
*   **`KNOWN_TAGS`**: A dictionary mapping tag names to emoji representations for visual display.
*   **`LakeViewStep` Dataclass**: Represents a single Lakeview-summarized step, containing the extracted task description, details, and emoji tags.
*   **`LakeView` Class**:
    *   **`__init__()`**: Initializes `LakeView` with a `LakeviewConfig`, setting up a dedicated `LLMClient` (`lakeview_llm_client`) for analysis.
    *   **`get_label()`**: Formats a list of tags into a human-readable string with optional emojis.
    *   **`extract_task_in_step()`**: Asynchronously calls the `lakeview_llm_client` with `EXTRACTOR_PROMPT` to get the task description and details for a given step. Includes retry logic for robust extraction.
    *   **`extract_tag_in_step()`**: Asynchronously calls the `lakeview_llm_client` with `TAGGER_PROMPT` to get the relevant tags for a step. Includes retry logic and validation against `KNOWN_TAGS`.
    *   **`_agent_step_str()`**: Converts an `AgentStep` object into a string representation suitable for LLM input.
    *   **`create_lakeview_step()`**: The main method to generate a `LakeViewStep` from an `AgentStep`, orchestrating the calls to `extract_task_in_step` and `extract_tag_in_step`.

This feature is crucial for improving the interpretability and transparency of the agent's complex decision-making process, making it easier for human users to understand the agent's progress and actions at a high level.

---

## `coding_tools_mcp/utils/legacy_config.py`

This file defines the `LegacyConfig` class, which is responsible for parsing and managing older JSON-based configuration files. It includes dataclasses for `ModelParameters`, `LakeviewConfig`, and `MCPServerConfig`, mirroring the structure of the newer YAML configuration but specifically tailored for the legacy format. This file is essentially a compatibility layer, allowing the system to still function with outdated configuration schemas.

**Key components and functionalities:**

*   **`ModelParameters` Dataclass**: Defines parameters for models in the legacy format (model name, API key, max tokens, temperature, etc.).
*   **`LakeviewConfig` Dataclass**: Configuration for Lakeview in the legacy format.
*   **`MCPServerConfig` Dataclass**: Configuration for MCP servers in the legacy format (similar to the new `MCPServerConfig`).
*   **`LegacyConfig` Class**:
    *   **`__init__()`**: Loads configuration from a specified JSON `config_file` (defaulting to `trae_config.json`) or a direct dictionary.
    *   Parses and populates `default_provider`, `max_steps`, `model_providers`, `mcp_servers`, `enable_lakeview`, and `allow_mcp_servers` from the loaded configuration.
    *   Provides default values for `model_providers` if none are specified.
    *   Configures `lakeview_config` based on the `enable_lakeview` flag and existing model providers.
    *   Includes a `__str__` representation for debugging.

This file is a necessary component for maintaining backward compatibility, ensuring that users with older configuration files can still run the agent without requiring manual migration to the new YAML format.

---

## `coding_tools_mcp/utils/mcp_client.py`

This file defines the `MCPClient` class, which is responsible for establishing and managing connections to external MCP (Model Context Protocol) servers. It handles the `stdio` transport mechanism (with `http` and `websocket` transports noted as "not implemented yet"), connects to the server, discovers available tools, and wraps them into `MCPTool` instances for the agent to use. It also manages the connection status and provides cleanup functionality.

**Key components and functionalities:**

*   **`MCPServerStatus` Enum**: Defines the connection status of an MCP server (`DISCONNECTED`, `CONNECTING`, `CONNECTED`).
*   **`MCPDiscoveryState` Enum**: Defines the state of the MCP tool discovery process.
*   **`MCPClient` Class**:
    *   **`__init__()`**: Initializes the client, including an `AsyncExitStack` for managing asynchronous contexts and a dictionary to track `mcp_servers_status`.
    *   **`get_mcp_server_status()` and `update_mcp_server_status()`**: Methods to query and update the connection status of a specific MCP server.
    *   **`connect_and_discover()`**: The main asynchronous method to connect to an MCP server and discover its tools.
        *   Selects the appropriate transport mechanism (currently only `stdio_client` is implemented).
        *   Calls `connect_to_server()` to establish the connection.
        *   Calls `list_tools()` to retrieve the tools provided by the server.
        *   Wraps each discovered tool into an `MCPTool` instance and appends it to `mcp_tools_container`.
        *   Includes error handling and cleanup for connection failures.
    *   **`connect_to_server()`**: Establishes a `ClientSession` with the MCP server using the provided transport. Updates the server status.
    *   **`call_tool()`**: Calls a specific tool on the connected MCP server.
    *   **`list_tools()`**: Lists all tools available from the connected MCP server.
    *   **`cleanup()`**: Closes the `AsyncExitStack` to clean up resources and updates the server status to `DISCONNECTED`.

This client is a fundamental enabler for the agent's extensibility, allowing it to dynamically integrate and leverage capabilities from external services that adhere to the Model Context Protocol.

---

## `coding_tools_mcp/utils/trajectory_recorder.py`

This file defines the `TrajectoryRecorder` class, a crucial component for debugging, analysis, and reproducibility of agent behavior. It meticulously logs every significant event during an agent's execution, including task details, LLM interactions, agent steps, and overall execution metadata, saving this data to a JSON file.

**Key functionalities:**

*   **`__init__()`**: Initializes the recorder. If no `trajectory_path` is provided, it auto-generates a timestamped JSON file path within a `trajectories/` subdirectory under `LOCAL_STORAGE_PATH`. It also initializes the `trajectory_data` dictionary with default fields.
*   **`start_recording()`**: Initializes the `trajectory_data` with task-specific information (task description, LLM provider/model, max steps) and records the start time.
*   **`record_llm_interaction()`**: Logs details of each interaction with an LLM, including input messages, the LLM's response (content, model, finish reason, token usage, tool calls), and the tools available at that moment.
*   **`record_agent_step()`**: Logs details of each individual agent execution step, including its number, state, associated LLM messages/response, tool calls, tool results, agent reflection, and any errors.
*   **`update_lakeview()`**: Updates a specific agent step in the trajectory data with its Lakeview summary.
*   **`finalize_recording()`**: Records the end time, success status, final result, and total execution time for the entire task.
*   **`save_trajectory()`**: Persists the `trajectory_data` dictionary to the specified JSON file, ensuring the directory exists. Includes error handling for file operations.
*   **`_serialize_message()`, `_serialize_tool_call()`, `_serialize_tool_result()`**: Helper methods to convert internal dataclass objects (`LLMMessage`, `ToolCall`, `ToolResult`) into serializable dictionary formats for JSON storage.
*   **`get_trajectory_path()`**: Returns the absolute path where the trajectory is being saved.

This recorder is indispensable for understanding the agent's decision-making process, debugging unexpected behaviors, and replaying past executions for analysis or improvement.

---

## `coding_tools_mcp/utils/cli/cli_console.py`

This file defines the abstract `CLIConsole` base class, which serves as the interface for all command-line console implementations. It establishes the contract for how the agent interacts with the user, including methods for starting/stopping the console, updating status, printing messages, and getting user input. It also defines enums for console modes and types, and includes a helper function for generating rich tables for agent step display.

**Key components and functionalities:**

*   **`ConsoleMode` Enum**: Defines the two primary modes of console operation: `RUN` (for single task execution) and `INTERACTIVE` (for continuous user interaction).
*   **`ConsoleType` Enum**: Defines the available console types: `SIMPLE` (basic text-based) and `RICH` (Textual TUI-based).
*   **`AGENT_STATE_INFO`**: A dictionary mapping `AgentStepState` to display information (color, emoji) for visual feedback.
*   **`ConsoleStep` Dataclass**: A helper dataclass to track the display status of each agent step within the console.
*   **`CLIConsole` (Abstract Base Class)**:
    *   **`__init__()`**: Initializes the console with a `mode` and optional `LakeviewConfig`. Sets up `lake_view` instance if configured.
    *   **Abstract Methods**:
        *   `start()`: Starts the console display.
        *   `update_status()`: Updates the console with current agent step and execution information.
        *   `print_task_details()`: Prints initial task configuration.
        *   `print()`: Prints a formatted message.
        *   `get_task_input()`: Gets task input from the user (for interactive mode).
        *   `get_working_dir_input()`: Gets working directory input from the user (for interactive mode).
        *   `stop()`: Stops the console and cleans up resources.
    *   **`set_lakeview()`**: Configures the `LakeView` instance for the console.
*   **`generate_agent_step_table()`**: A helper function that takes an `AgentStep` and generates a `rich.table.Table` representation of its details, including LLM response, tool calls, tool results, reflection, and errors.

This file is the fundamental interface for all user-facing console interactions, ensuring a consistent API for different console implementations and enabling clear communication of the agent's progress.

---

## `coding_tools_mcp/utils/cli/console_factory.py`

This file implements the `ConsoleFactory` class, a simple but effective factory pattern for instantiating different types of `CLIConsole` implementations (`SimpleCLIConsole` or `RichCLIConsole`). It also provides a static method to suggest the most suitable console based on the operation mode.

**Key functionalities:**

*   **`ConsoleFactory` Class**:
    *   **`create_console()` Static Method**:
        *   Takes `console_type`, `mode`, and `lakeview_config` as input.
        *   Returns an instance of `SimpleCLIConsole` or `RichCLIConsole` based on `console_type`.
        *   Raises `ValueError` if an unsupported `console_type` is provided.
    *   **`get_recommended_console_type()` Static Method**:
        *   Takes a `ConsoleMode` as input.
        *   Recommends `ConsoleType.RICH` for `INTERACTIVE` mode due to its superior user experience.
        *   Recommends `ConsoleType.SIMPLE` for `RUN` mode, which is suitable for non-interactive execution.

This factory abstracts away the complexity of console creation, ensuring that the correct console implementation is used based on the desired type and mode, without the calling code needing to directly manage specific class imports or instantiation logic.

---

## `coding_tools_mcp/utils/cli/rich_console.py`

This file implements the `RichCLIConsole`, a sophisticated command-line interface that leverages the `Textual` TUI (Text User Interface) framework to provide a rich, interactive experience. It extends `CLIConsole` and includes a nested `RichConsoleApp` class, which is the actual Textual application.

**Key components and functionalities:**

*   **`TokenDisplay` Static Widget**: A `Textual` widget to display real-time token usage (total, input, output) in the footer of the TUI.
*   **`RichConsoleApp` (Textual App)**: The core Textual application that defines the TUI layout and handles user interactions.
    *   **`CSS`**: Defines the styling for the TUI elements (containers, logs, input).
    *   **`BINDINGS`**: Keyboard shortcuts for common actions (e.g., `ctrl+c` to quit).
    *   **`compose()`**: Defines the UI layout, yielding `Header`, `RichLog` (for execution output), `Input` (for interactive tasks), `Static` (for task display), `TokenDisplay`, and `Footer`.
    *   **`on_mount()`**: Called when the app is mounted, sets the title, queries for widgets, and focuses the input field.
    *   **`on(Input.Submitted)` handler**: Handles user input from the `Input` widget.
        *   Processes commands like `exit`, `quit`, `help`, `clear`, `status`.
        *   If a task is entered, it sets the `current_task`, updates the task display, and asynchronously calls `_execute_task()`.
    *   **`_execute_task()`**: Asynchronously runs the agent's task, handling working directory, task arguments, and logging output to the `RichLog`. Includes error handling.
    *   **`log_agent_step()`**: Formats and logs an `AgentStep` to the `RichLog` using `rich.panel.Panel` and `generate_agent_step_table`.
    *   **`action_quit()`**: Handles quitting the application.
*   **`RichCLIConsole` Class**: Inherits from `CLIConsole`.
    *   **`__init__()`**: Initializes the console, setting up internal flags and storing agent context for interactive mode.
    *   **`start()` (override)**: Starts the `RichConsoleApp` asynchronously.
    *   **`update_status()` (override)**: Updates the `RichConsoleApp`'s display with agent step information and token usage. It ensures steps are logged only once when they reach `COMPLETED` or `ERROR` state.
    *   **`print_task_details()` (override)**: Prints initial task details to the `RichLog` in a `Panel`.
    *   **`print()` (override)**: Prints a formatted message to the `RichLog`.
    *   **`get_task_input()` and `get_working_dir_input()` (override)**: These methods are not directly used for input in the TUI, as input is handled by Textual widgets.
    *   **`stop()` (override)**: Signals the Textual app to exit.
    *   **`set_agent_context()`**: Sets the agent and its configuration within the console, allowing the `RichConsoleApp` to execute tasks.
    *   **`set_initial_task()`**: Sets the initial task string for display in `RUN` mode.

This file provides a highly interactive and visually informative user experience, making it easier to monitor and control the agent's execution, especially in complex, multi-step scenarios.

---

## `coding_tools_mcp/utils/cli/simple_console.py`

This file implements the `SimpleCLIConsole`, a basic text-based command-line interface for the agent. It extends `CLIConsole` and uses the `rich` library for basic formatting (colors, panels, tables) but without the full TUI capabilities of `RichCLIConsole`.

**Key functionalities:**

*   **`__init__()`**: Initializes the console with a `rich.console.Console` instance.
*   **`update_status()` (override)**: Updates the console status. It prints agent step updates when they reach `COMPLETED` or `ERROR` states. If Lakeview is enabled, it asynchronously generates and stores Lakeview summaries for these steps.
*   **`start()` (override)**: This method is designed to be awaited. It waits until the agent's execution is complete (either `COMPLETED` or `ERROR` state), then prints a comprehensive Lakeview summary (if enabled) and a final execution summary.
*   **`_print_step_update()`**: Formats and prints individual agent steps using `generate_agent_step_table`, including LLM token usage.
*   **`_print_lakeview_summary()`**: Iterates through completed steps and prints their generated Lakeview panels, providing a high-level overview of the agent's actions.
*   **`_print_execution_summary()`**: Presents a final summary of the task execution, including task name, success status, number of steps, execution time, and total token usage. It also displays the `final_result` in a `rich.panel.Panel`.
*   **`print_task_details()` (override)**: Prints initial task configuration details using a `rich.panel.Panel`.
*   **`print()` (override)**: Prints a formatted message to the console using `rich`.
*   **`get_task_input()` (override)**: Prompts the user for task input in interactive mode using `input()`. Handles `exit`/`quit` commands.
*   **`get_working_dir_input()` (override)**: Prompts the user for the working directory in interactive mode using `input()`.
*   **`stop()` (override)**: A no-op for the simple console, as it doesn't require explicit cleanup.
*   **`_create_lakeview_step_display()`**: Asynchronously calls `lake_view.create_lakeview_step` to generate a `LakeViewStep` and formats it into a `rich.panel.Panel` for display.

This console provides a straightforward, line-by-line view of the agent's progress, suitable for basic logging and non-interactive execution, while still leveraging `rich` for improved readability and optional Lakeview summaries.

---

## `coding_tools_mcp/utils/llm_clients/anthropic_client.py`

This file implements the `AnthropicClient`, a specialized LLM client for interacting with Anthropic's API. It extends `BaseLLMClient` and handles the specifics of converting internal `LLMMessage` and `Tool` objects into Anthropic's `MessageParam` and `ToolUnionParam` formats, respectively. It also parses Anthropic's responses back into the agent's internal `LLMResponse` and `ToolCall` structures. Crucially, it integrates retry logic for API calls and records all LLM interactions via the `TrajectoryRecorder`.

**Key functionalities:**

*   **`__init__()`**: Initializes the `AnthropicClient` with a `ModelConfig` and creates an `anthropic.Anthropic` client instance using the provided API key and base URL. It also initializes `message_history` and `system_message`.
*   **`set_chat_history()` (override)**: Sets the internal `message_history` by parsing a list of `LLMMessage` objects into Anthropic's format.
*   **`_create_anthropic_response()`**: A private method that makes the actual API call to `self.client.messages.create()`. This method is decorated with `retry_with` to handle transient errors.
*   **`chat()` (override)**: The main method for sending chat messages to Anthropic.
    *   Parses incoming `LLMMessage` objects into Anthropic's format.
    *   Manages `message_history` based on `reuse_history`.
    *   Converts `Tool` objects into Anthropic's `ToolUnionParam` schema, with special handling for built-in tools like "str_replace_based_edit_tool" and "bash" that have predefined Anthropic tool types.
    *   Calls `_create_anthropic_response()` (with retry logic).
    *   Parses the Anthropic API response: extracts text content and `tool_use` blocks, converting them into `LLMResponse` and `ToolCall` objects.
    *   Updates `LLMUsage` from the response.
    *   Records the LLM interaction using `TrajectoryRecorder`.
*   **`parse_messages()`**: Converts a list of `LLMMessage` objects into Anthropic's `MessageParam` format, handling `system` messages (which are set as `system_message` for the API call), `tool_result` messages, `tool_call` messages, and regular `user`/`assistant` text messages.
*   **`parse_tool_call()`**: Converts an internal `ToolCall` object into an Anthropic `ToolUseBlockParam`.
*   **`parse_tool_call_result()`**: Converts an internal `ToolResult` object into an Anthropic `ToolResultBlockParam`, including error information.

This client is essential for enabling the agent to communicate effectively with Anthropic's powerful LLMs, ensuring proper message formatting, tool integration, and robust API interaction.

---

## `coding_tools_mcp/utils/llm_clients/azure_client.py`

This file implements the `AzureClient`, which is a specialized LLM client for interacting with Azure OpenAI Service models. It extends `OpenAICompatibleClient` and uses an `AzureProvider` configuration to handle the specific authentication and endpoint requirements of Azure.

**Key components and functionalities:**

*   **`AzureProvider` Class**: Inherits from `ProviderConfig` (from `openai_compatible_base.py`).
    *   **`create_client()` (override)**: Creates an `openai.AzureOpenAI` client instance, requiring `azure_endpoint` (mapped from `base_url`), `api_version`, and `api_key`.
    *   **`get_service_name()`**: Returns "Azure OpenAI" for logging.
    *   **`get_provider_name()`**: Returns "azure" for trajectory recording.
    *   **`get_extra_headers()`**: Returns an empty dictionary, as no special headers are needed for Azure.
    *   **`supports_tool_calling()`**: Returns `True`, as Azure OpenAI models generally support tool calling.
*   **`AzureClient` Class**: Inherits from `OpenAICompatibleClient`.
    *   **`__init__()`**: Initializes the `AzureClient` by calling the `OpenAICompatibleClient` constructor with the provided `ModelConfig` and an instance of `AzureProvider`.

This client provides a seamless integration with Azure OpenAI Service, allowing the agent to leverage Azure-deployed LLMs while maintaining compatibility with the shared logic defined in `OpenAICompatibleClient`.

---

## `coding_tools_mcp/utils/llm_clients/base_client.py`

This file defines the abstract `BaseLLMClient` class, which serves as the foundational interface for all LLM client implementations within the system. It establishes the core contract for how the agent interacts with various large language models, ensuring a consistent API regardless of the underlying provider.

**Key functionalities:**

*   **`__init__()`**: Initializes the base client with `api_key`, `base_url`, and `api_version` extracted from the `ModelConfig`. It also initializes `trajectory_recorder` to `None`, which can be set later.
*   **`set_trajectory_recorder()`**: A method to set the `TrajectoryRecorder` instance for the client, enabling logging of LLM interactions.
*   **`set_chat_history()` (abstract method)**: An abstract method that must be implemented by subclasses to set the internal chat history of the LLM client.
*   **`chat()` (abstract method)**: The core abstract method for sending chat messages to the LLM. Subclasses must implement this to handle message formatting, API calls, and response parsing specific to their LLM provider. It takes `messages`, `model_config`, optional `tools`, and a `reuse_history` flag.
*   **`supports_tool_calling()`**: A concrete method that checks if the model configured in `ModelConfig` supports tool calling based on its `supports_tool_calling` attribute.

This file is crucial for maintaining a clean and extensible architecture for LLM integrations, ensuring that new LLM providers can be added by simply implementing this abstract interface.

---

## `coding_tools_mcp/utils/llm_clients/doubao_client.py`

This file implements the `DoubaoClient`, a specialized LLM client for interacting with Doubao models. Similar to `AzureClient`, it extends `OpenAICompatibleClient` and uses a `DoubaoProvider` to configure the OpenAI client with the specific base URL for Doubao.

**Key components and functionalities:**

*   **`DoubaoProvider` Class**: Inherits from `ProviderConfig`.
    *   **`create_client()` (override)**: Creates an `openai.OpenAI` client instance, using the provided `base_url` and `api_key`.
    *   **`get_service_name()`**: Returns "Doubao" for logging.
    *   **`get_provider_name()`**: Returns "doubao" for trajectory recording.
    *   **`get_extra_headers()`**: Returns an empty dictionary, as no special headers are needed.
    *   **`supports_tool_calling()`**: Returns `True`, as Doubao models generally support tool calling.
*   **`DoubaoClient` Class**: Inherits from `OpenAICompatibleClient`.
    *   **`__init__()`**: Initializes the `DoubaoClient` by calling the `OpenAICompatibleClient` constructor with the provided `ModelConfig` and an instance of `DoubaoProvider`.

This client enables the agent to seamlessly integrate with Doubao's LLM services, maintaining compatibility with the OpenAI API while adapting to Doubao's specific endpoint.

---

## `coding_tools_mcp/utils/llm_clients/google_client.py`

This file implements the `GoogleClient`, a specialized LLM client for interacting with Google Gemini API models. It extends `BaseLLMClient` and handles the intricate details of converting internal `LLMMessage` and `Tool` objects into Gemini's `Content` and `FunctionDeclaration` formats, respectively. It also parses Gemini's responses back into the agent's internal `LLMResponse` and `ToolCall` structures. Crucially, it integrates retry logic for API calls and records all LLM interactions via the `TrajectoryRecorder`.

**Key functionalities:**

*   **`__init__()`**: Initializes the `GoogleClient` with a `ModelConfig` and creates a `genai.Client` instance using the provided API key. It also initializes `message_history` and `system_instruction`.
*   **`set_chat_history()` (override)**: Sets the internal `message_history` and `system_instruction` by parsing a list of `LLMMessage` objects into Gemini's format.
*   **`_create_google_response()`**: A private method that makes the actual API call to `self.client.models.generate_content()`. This method is decorated with `retry_with` to handle transient errors.
*   **`chat()` (override)**: The main method for sending chat messages to Google Gemini.
    *   Parses incoming `LLMMessage` objects into Gemini's `Content` format, separating system instructions.
    *   Manages `message_history` based on `reuse_history`.
    *   Sets up `types.GenerateContentConfig` with model parameters (temperature, top_p, top_k, max tokens, candidate count, stop sequences, system instruction).
    *   Converts `Tool` objects into Gemini's `types.Tool` schema with `FunctionDeclaration` for tool calling.
    *   Calls `_create_google_response()` (with retry logic).
    *   Parses the Gemini API response: extracts text content and `function_call` parts, converting them into `LLMResponse` and `ToolCall` objects.
    *   Updates `LLMUsage` from the response.
    *   Records the LLM interaction using `TrajectoryRecorder`.
*   **`parse_messages()`**: Converts a list of `LLMMessage` objects into Gemini's `types.Content` format, specifically handling `system` messages (which are extracted as `system_instruction`), `tool_result` messages, `tool_call` messages, and regular `user`/`model` text messages.
*   **`parse_tool_call()`**: Converts an internal `ToolCall` object into a Gemini `types.Part` representing a function call.
*   **`parse_tool_call_result()`**: Converts an internal `ToolResult` object into a Gemini `types.Part` representing a function response, including error information and handling JSON serialization issues for results.

This client is essential for enabling the agent to communicate effectively with Google's Gemini models, ensuring proper message formatting, tool integration, and robust API interaction.

---

## `coding_tools_mcp/utils/llm_clients/llm_basics.py`

This file defines fundamental dataclasses for standardizing LLM interactions: `LLMMessage`, `LLMUsage`, and `LLMResponse`. These dataclasses provide a consistent, structured way to represent LLM data across different providers, facilitating interoperability and analysis.

**Key components:**

*   **`LLMMessage` Dataclass**: Represents a single message in a conversation.
    *   `role`: The role of the message sender (e.g., "system", "user", "assistant").
    *   `content`: The text content of the message (optional).
    *   `tool_call`: An optional `ToolCall` object if the message represents a tool call from the LLM.
    *   `tool_result`: An optional `ToolResult` object if the message represents the result of a tool execution.
*   **`LLMUsage` Dataclass**: Tracks token consumption during LLM interactions.
    *   `input_tokens`: Number of tokens in the input prompt/messages.
    *   `output_tokens`: Number of tokens in the LLM's response.
    *   `cache_creation_input_tokens`: Tokens used for creating cache entries.
    *   `cache_read_input_tokens`: Tokens read from cache.
    *   `reasoning_tokens`: Tokens specifically used for reasoning (if provided by the LLM).
    *   **`__add__()`**: Overloads the addition operator to allow summing `LLMUsage` objects, useful for aggregating token usage across multiple steps.
    *   **`__str__()`**: Provides a string representation for debugging.
*   **`LLMResponse` Dataclass**: Encapsulates the LLM's response.
    *   `content`: The main text content of the LLM's response.
    *   `usage`: An optional `LLMUsage` object detailing token consumption.
    *   `model`: The name of the LLM model that generated the response.
    *   `finish_reason`: The reason the LLM stopped generating (e.g., "stop", "tool_calls").
    *   `tool_calls`: An optional list of `ToolCall` objects if the LLM requested tool execution.

These dataclasses are fundamental for maintaining a clear and consistent data flow throughout the agent's interaction with various LLMs and for enabling comprehensive logging and analysis of token usage.

---

## `coding_tools_mcp/utils/llm_clients/llm_client.py`

This file defines the main `LLMClient` class, which acts as a central dispatcher for interacting with various LLM providers. It provides a unified interface for sending chat messages and managing chat history, abstracting away the provider-specific implementations.

**Key components and functionalities:**

*   **`LLMProvider` Enum**: Defines all supported LLM providers (OpenAI, Anthropic, Azure, Ollama, OpenRouter, Doubao, Google).
*   **`LLMClient` Class**:
    *   **`__init__()`**: Initializes the client. It takes a `ModelConfig` and dynamically instantiates the appropriate provider-specific client (e.g., `OpenAIClient`, `AnthropicClient`, `AzureClient`, etc.) based on `model_config.model_provider.provider`. This uses a `match` statement for clear dispatching.
    *   **`set_trajectory_recorder()`**: Passes the `TrajectoryRecorder` instance to the underlying provider-specific client, enabling it to log LLM interactions.
    *   **`set_chat_history()`**: Delegates the call to the underlying provider-specific client to set its chat history.
    *   **`chat()`**: Delegates the chat message sending to the underlying provider-specific client. This is the primary method for the agent to communicate with an LLM.
    *   **`supports_tool_calling()`**: Checks if the currently active LLM client (and its configured model) supports tool calling.

This file is a critical architectural component, implementing the Factory pattern to provide a flexible and extensible way to integrate with multiple LLM providers. It ensures that the rest of the agent's codebase can interact with any LLM through a single, consistent interface.

---

## `coding_tools_mcp/utils/llm_clients/ollama_client.py`

This file implements the `OllamaClient`, a specialized LLM client for interacting with local Ollama models. It extends `BaseLLMClient` and adapts the OpenAI client to work with Ollama's API, handling message parsing, tool schema generation, and response processing. It also integrates retry logic and trajectory recording.

**Key functionalities:**

*   **`__init__()`**: Initializes the `OllamaClient` with a `ModelConfig`. It creates an `openai.OpenAI` client instance, setting the `base_url` to Ollama's default (`http://localhost:11434/v1`) if not specified in the config. It also initializes `message_history`.
*   **`set_chat_history()` (override)**: Sets the internal `message_history` by parsing a list of `LLMMessage` objects into Ollama's (OpenAI-compatible) format.
*   **`_create_ollama_response()`**: A private method that makes the actual API call to `ollama.chat()`. This method is decorated with `retry_with` to handle transient errors. It specifically formats tool schemas for Ollama's `tools` parameter.
*   **`chat()` (override)**: The main method for sending chat messages to Ollama.
    *   Parses incoming `LLMMessage` objects into Ollama's (OpenAI-compatible) format.
    *   Converts `Tool` objects into `FunctionToolParam` for Ollama's tool schema.
    *   Manages `message_history` based on `reuse_history`.
    *   Calls `_create_ollama_response()` (with retry logic).
    *   Parses the Ollama API response: extracts text content or `tool_calls`, converting them into `LLMResponse` and `ToolCall` objects. (Note: `usage` and `finish_reason` are currently not fully extracted from Ollama's response).
    *   Records the LLM interaction using `TrajectoryRecorder`.
*   **`parse_messages()`**: Converts a list of `LLMMessage` objects into Ollama's (OpenAI-compatible) message format, handling `tool_result`, `tool_call`, `system`, `user`, and `assistant` messages.
*   **`parse_tool_call()`**: Converts an internal `ToolCall` object into an Ollama (OpenAI-compatible) `ResponseFunctionToolCallParam`.
*   **`parse_tool_call_result()`**: Converts an internal `ToolResult` object into an Ollama (OpenAI-compatible) `FunctionCallOutput`.
*   **`_id_generator()`**: Generates a UUID for tool call IDs.

This client is crucial for enabling the agent to utilize locally hosted LLMs via Ollama, providing flexibility in deployment and reducing reliance on external cloud services, while maintaining a consistent interface.

---

## `coding_tools_mcp/utils/llm_clients/openai_client.py`

This file implements the `OpenAIClient`, a specialized LLM client for interacting with OpenAI's API. It extends `BaseLLMClient` and handles the specifics of converting internal `LLMMessage` and `Tool` objects into OpenAI's API request formats. It also parses OpenAI's responses back into the agent's internal `LLMResponse` and `ToolCall` structures. Crucially, it integrates retry logic for API calls and records all LLM interactions via the `TrajectoryRecorder`.

**Key functionalities:**

*   **`__init__()`**: Initializes the `OpenAIClient` with a `ModelConfig` and creates an `openai.OpenAI` client instance using the provided API key and base URL. It also initializes `message_history`.
*   **`set_chat_history()` (override)**: Sets the internal `message_history` by parsing a list of `LLMMessage` objects into OpenAI's format.
*   **`_create_openai_response()`**: A private method that makes the actual API call to `self.client.responses.create()`. This method is decorated with `retry_with` to handle transient errors. It conditionally omits `temperature` for certain OpenAI models (e.g., "o3", "o4-mini", "gpt-5").
*   **`chat()` (override)**: The main method for sending chat messages to OpenAI.
    *   Parses incoming `LLMMessage` objects into OpenAI's `ResponseInputParam` format.
    *   Manages `message_history` based on `reuse_history`.
    *   Converts `Tool` objects into OpenAI's `FunctionToolParam` schema for tool calling.
    *   Calls `_create_openai_response()` (with retry logic).
    *   Parses the OpenAI API response: extracts text content and `function_call` blocks, converting them into `LLMResponse` and `ToolCall` objects.
    *   Updates `LLMUsage` from the response, including `cache_read_input_tokens` and `reasoning_tokens` if available.
    *   Records the LLM interaction using `TrajectoryRecorder`.
*   **`parse_messages()`**: Converts a list of `LLMMessage` objects into OpenAI's `ResponseInputParam` format, handling `tool_result`, `tool_call`, `system`, `user`, and `assistant` messages.
*   **`parse_tool_call()`**: Converts an internal `ToolCall` object into an OpenAI `ResponseFunctionToolCallParam`.
*   **`parse_tool_call_result()`**: Converts an internal `ToolResult` object into an OpenAI `FunctionCallOutput`, including error information.

This client is essential for enabling the agent to communicate effectively with OpenAI's powerful LLMs, ensuring proper message formatting, tool integration, and robust API interaction.

---

## `coding_tools_mcp/utils/llm_clients/openai_compatible_base.py`

This file defines the `OpenAICompatibleClient` abstract base class, which serves as a common foundation for LLM clients that interact with OpenAI-like APIs (e.g., Azure, Doubao, Ollama, OpenRouter). It abstracts away the shared logic for client creation, message parsing, tool schema generation, chat interaction, response parsing, and trajectory recording, promoting code reuse and consistency.

**Key components and functionalities:**

*   **`ProviderConfig` (Abstract Base Class)**: An abstract interface for provider-specific configurations. Subclasses must implement:
    *   `create_client()`: Creates the specific `openai.OpenAI` client instance.
    *   `get_service_name()`: Returns the service name for logging.
    *   `get_provider_name()`: Returns the provider name for trajectory recording.
    *   `get_extra_headers()`: Returns any extra HTTP headers needed.
    *   `supports_tool_calling()`: Checks if a model supports tool calling.
*   **`OpenAICompatibleClient` Class**: Inherits from `BaseLLMClient`.
    *   **`__init__()`**: Initializes the client with a `ModelConfig` and a `ProviderConfig` instance. It uses `provider_config.create_client()` to get the actual OpenAI client.
    *   **`set_chat_history()` (override)**: Sets the internal `message_history` by parsing `LLMMessage` objects into OpenAI's `ChatCompletionMessageParam` format.
    *   **`_create_response()`**: A private method that makes the actual API call to `self.client.chat.completions.create()`. This method is decorated with `retry_with` and handles `extra_headers`. It conditionally omits `temperature` for certain models.
    *   **`chat()` (override)**: The main method for sending chat messages.
        *   Parses incoming `LLMMessage` objects.
        *   Manages `message_history` based on `reuse_history`.
        *   Converts `Tool` objects into OpenAI's `ChatCompletionToolParam` schema for tool calling.
        *   Calls `_create_response()` (with retry logic).
        *   Parses the OpenAI API response: extracts text content and `tool_calls`, converting them into `LLMResponse` and `ToolCall` objects.
        *   Updates `message_history` with the assistant's response.
        *   Records the LLM interaction using `TrajectoryRecorder`.
    *   **`parse_messages()`**: Converts a list of `LLMMessage` objects into OpenAI's `ChatCompletionMessageParam` format. It dispatches to helper functions (`_msg_tool_call_handler`, `_msg_tool_result_handler`, `_msg_role_handler`) based on message type.
*   **Helper Functions (`_msg_tool_call_handler`, `_msg_tool_result_handler`, `_msg_role_handler`)**: These functions handle the specific conversion logic for different types of `LLMMessage` objects into their corresponding OpenAI API message formats.

This file is a crucial abstraction that prevents code duplication and ensures consistency across various OpenAI-compatible LLM integrations, making it easier to add new providers that adhere to this API standard.

---

## `coding_tools_mcp/utils/llm_clients/openrouter_client.py`

This file implements the `OpenRouterClient`, a specialized LLM client for interacting with models available through the OpenRouter API. It extends `OpenAICompatibleClient` and uses an `OpenRouterProvider` to configure the OpenAI client with OpenRouter's specific base URL and to add custom headers for attribution. It also includes logic to determine if a given model on OpenRouter supports tool calling.

**Key components and functionalities:**

*   **`OpenRouterProvider` Class**: Inherits from `ProviderConfig`.
    *   **`create_client()` (override)**: Creates an `openai.OpenAI` client instance, using the provided `api_key` and `base_url` (which defaults to `https://openrouter.ai/api/v1` if not explicitly set).
    *   **`get_service_name()`**: Returns "OpenRouter" for logging.
    *   **`get_provider_name()`**: Returns "openrouter" for trajectory recording.
    *   **`get_extra_headers()`**: Adds OpenRouter-specific headers (`HTTP-Referer` and `X-Title`) if corresponding environment variables (`OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME`) are set.
    *   **`supports_tool_calling()`**: Checks if a given `model_name` (from OpenRouter) supports tool calling by looking for specific patterns (e.g., "gpt-4", "claude-3", "gemini") in the model name.
*   **`OpenRouterClient` Class**: Inherits from `OpenAICompatibleClient`.
    *   **`__init__()`**: Initializes the `OpenRouterClient` by calling the `OpenAICompatibleClient` constructor with the provided `ModelConfig` and an instance of `OpenRouterProvider`. It also sets a default `base_url` for OpenRouter if none is provided in the `ModelConfig`.

This client is another crucial piece for enabling the agent to leverage a wide array of LLMs from different providers, preventing vendor lock-in and allowing access to a broader range of models available through the OpenRouter platform.

---

## `coding_tools_mcp/utils/llm_clients/readme.md`

This file is a placeholder `README.md` within the `llm_clients` directory. It contains a single, brief note: "Refactor the list of models into a more robust and developer-friendly format."

**Purpose:**

*   Serves as a reminder or a future task item for refactoring the model listing mechanism within the LLM client infrastructure.
*   Does not contain any executable code or direct functional impact on the current system.

This file indicates an area identified for future improvement or refactoring within the project.

---

## `coding_tools_mcp/utils/llm_clients/retry_utils.py`

This file provides a `retry_with` decorator, a crucial utility for enhancing the robustness of API calls, particularly to LLMs. It implements a retry mechanism with randomized exponential backoff, preventing transient network issues or API rate limits from completely derailing the agent's operation.

**Key functionalities:**

*   **`retry_with()` Decorator**:
    *   Takes `func` (the function to decorate), `provider_name` (for logging), and `max_retries` as arguments.
    *   Uses `functools.wraps` to preserve metadata of the decorated function.
    *   The `wrapper` function attempts to execute `func` up to `max_retries + 1` times.
    *   If an exception occurs, it catches it, prints an informative message (including the provider name and error), and then `time.sleep()` for a random duration between 3 and 30 seconds before retrying.
    *   If all retries fail, it re-raises the last encountered exception.

This utility is essential for building resilient LLM-powered applications, as it gracefully handles common API and network instabilities, significantly improving the overall reliability of the agent's interactions with external services.
