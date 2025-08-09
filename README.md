# Dev Tools MCP Server

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Dev Tools MCP Server** is a standalone server that exposes a powerful suite of tools for general-purpose software engineering tasks via the Model Context Protocol (MCP). It is designed to be used by any MCP-compatible client (such as an LLM agent) to perform file system operations, execute commands, interact with git, and more.

This server is built by extracting and adapting the battle-tested tool implementations from the Trae Agent project, repackaging them into a lightweight, independent, and easy-to-use service.

## ✨ Available Tools

This server provides the following tools:

-   **`bash`**: Executes arbitrary shell commands in a persistent session.
-   **`file_editor`**: A powerful tool for file manipulation (view, create, replace, insert).
-   **`json_editor`**: Precisely modifies JSON files using JSONPath expressions.
-   **`code_search`**: Intelligently searches a codebase for functions, classes, and methods using a Code Knowledge Graph (CKG).
-   **`git_diff`**: Retrieves the `git diff` for a repository, either for uncommitted changes or against a base commit.
-   **`sequential_thinking`**: A meta-tool for an agent to record and structure its multi-step reasoning process.
-   **`task_done`**: A simple signaling tool for an agent to indicate that it has completed its task.

## 🚀 Installation

### Requirements
- [UV](https://docs.astral.sh/uv/) (a fast Python package installer and resolver)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/olegische/coding-tools-mcp.git
    cd coding-tools-mcp
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    uv sync
    ```

3.  **Activate the virtual environment:**
    ```bash
    source .venv/bin/activate
    ```

## ⚙️ Configuration

The server can be configured using environment variables.

-   **`MCP_TRANSPORT`**: Sets the transport mechanism.
    -   Options: `"stdio"`, `"sse"`, `"http"`.
    -   Default: `"stdio"`.
-   **`MCP_HOST`**: The host address for the server to bind to (used for `http` and `sse` transports).
    -   Default: `"0.0.0.0"`.
-   **`MCP_PORT`**: The port for the server to listen on (used for `http` and `sse` transports).
    -   Default: `8660`.

### Example

To run the server over HTTP on port 9000:
```bash
export MCP_TRANSPORT=http
export MCP_PORT=9000
dev-tools-server
```

## 📖 Usage

To run the MCP server, simply execute the following command in your terminal:

```bash
dev-tools-server
```

The server will start and listen for connections from an MCP client. By default, it uses the `stdio` transport, which is ideal for local clients that manage the server as a subprocess. For network-based transports, ensure the host and port are configured correctly.

Any MCP-compatible client can now connect to this process and call the available tools.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
