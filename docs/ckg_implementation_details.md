# CKG: Incremental Indexing Implementation Details

This document describes the technical implementation of the new, granular indexing system for the Code Knowledge Graph (CKG). The system is designed for high performance, operational atomicity, and ease of integration.

## 1. Core Architectural Principles

1.  **Persistence and Isolation:** For each project (identified by the unique path to its root directory), a **single, persistent SQLite database** is created. This eliminates the need to recreate databases and ensures data isolation between projects.
2.  **File-Level Granularity:** The system has moved away from the concept of a full codebase "snapshot." Instead, change tracking occurs at the level of individual files by **hashing their content (MD5)**.
3.  **Atomic Transactions:** All update operations for a single file (deleting old records, inserting new ones, updating the hash) are performed as a **single atomic transaction**. This guarantees that the database is never left in a partially updated, inconsistent state, even if the parsing process is interrupted.
4.  **Incremental Updates:** The system is designed around live updates. The primary mechanism is the `on_file_changed()` method, which allows for targeted and efficient index updates for a single modified file.

---

## 2. Database Schema

The database file (`ckg_{hash_of_path}.db`) contains three main tables:

-   `functions`: Stores information about functions and methods.
-   `classes`: Stores information about classes.
-   `file_hashes`: The **new core table** of the incremental system.
    -   `file_path (TEXT, PRIMARY KEY)`: The absolute path to the file.
    -   `hash (TEXT)`: The MD5 hash of the file's content.

To accelerate queries by file path (a key operation when deleting old records), **indexes** have been added to the `file_path` field in both the `functions` and `classes` tables. `PRAGMA journal_mode=WAL` is also enabled to improve concurrency performance.

---

## 3. Core Components and Logic

### `CKGDatabase.__init__(codebase_path)`

-   When a `CKGDatabase` object is initialized for a specific `codebase_path`:
    1.  A path to the persistent database is generated based on a hash of the `codebase_path`.
    2.  A connection to the database is established.
    3.  `_create_tables()` is called to ensure all tables and indices exist.
    4.  `sync_codebase()` is launched to perform the initial synchronization.

### `sync_codebase()`

-   This method performs a full but "intelligent" synchronization of the index with the filesystem's state.
-   **Algorithm:**
    1.  Fetch the set of all file paths currently in the index from the `file_hashes` table (`db_files`).
    2.  Scan the project's filesystem (`codebase_path.glob("**/*")`) to build a set of file paths that *should* be indexed (`disk_files`), according to the filtering logic in `_should_index_file`.
    3.  For each file on disk:
        -   Calculate its current MD5 content hash.
        -   Compare it to the hash stored in the `file_hashes` table.
        -   If the hash is new or has changed, call `on_file_changed()` for that file to trigger a re-index.
    4.  For any file present in `db_files` but not in `disk_files`, call `_remove_file_from_index()` to handle deletions.

### `on_file_changed(file_path)`

-   This is the primary entry point for incremental updates and the core of the "live indexing" strategy.
-   **Algorithm:**
    1.  The entire method is wrapped in a `with self._db_connection:` block, making the operation atomic.
    2.  It calls `_db_connection.execute("DELETE ...")` to remove all existing `functions` and `classes` records associated with the given `file_path`.
    3.  It calls `_index_file(file_path)` to parse the file and insert the new symbol records.
    4.  It inserts or replaces the record in the `file_hashes` table with the new content hash for the file.

---

## 4. File Filtering Logic

The `_should_index_file(file_path)` method prevents non-source files and artifacts from being indexed. It returns `False` if:
-   The file or any of its parent directories is hidden (starts with a `.`).
-   The file's extension is not found in the `extension_to_language` mapping (e.g., `.pyc`, `.o`, `.so`, `.env` are all ignored).

---

## 5. Integration Guide

To make the CKG "live," any tool that modifies a file on disk **must** call the `on_file_changed()` method after a successful write operation.

**Example (conceptual):**

```python
# Inside a tool like TextEditorTool

class TextEditorTool:
    def __init__(self, indexing_service: CKGDatabase):
        self._indexing_service = indexing_service

    def write_file(self, path: Path, content: str):
        # ... logic to write file to disk ...
        file_path.write_text(content)

        # Trigger the CKG update
        self._indexing_service.on_file_changed(path)
