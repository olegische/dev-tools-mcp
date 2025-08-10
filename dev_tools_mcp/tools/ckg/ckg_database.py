# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

from tree_sitter import Node, Parser
from tree_sitter_languages import get_parser

from dev_tools_mcp.tools.ckg.base import ClassEntry, FunctionEntry, extension_to_language
from dev_tools_mcp.utils.constants import LOCAL_STORAGE_PATH

CKG_DATABASE_PATH = LOCAL_STORAGE_PATH / "ckg"
CKG_DATABASE_EXPIRY_TIME = 60 * 60 * 24 * 7  # 1 week in seconds

"""
Known issues:
1. When a subdirectory of a codebase that has already been indexed, the CKG is built again for this subdirectory.
2. The rebuilding logic can be improved by only rebuilding for files that have been modified.
3. For JavaScript and TypeScript, the AST is not complete: anonymous functions, arrow functions, etc., are not parsed.
"""

def _get_file_content_hash(file_path: Path) -> str:
    """Gets the MD5 hash of a file's content.

    Args:
        file_path: The path to the file.

    Returns:
        The MD5 hash as a hexadecimal string.
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def _get_database_path_for_codebase(codebase_path: Path) -> Path:
    """Generates a stable database path from the codebase path.

    This ensures that each codebase has its own unique, persistent database file.

    Args:
        codebase_path: The path to the codebase.

    Returns:
        The Path object for the SQLite database file.
    """
    codebase_hash = hashlib.md5(codebase_path.as_posix().encode()).hexdigest()
    return CKG_DATABASE_PATH / f"ckg_{codebase_hash}.db"


SQL_LIST = {
    "functions": """
    CREATE TABLE IF NOT EXISTS functions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        body TEXT NOT NULL,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        parent_function TEXT,
        parent_class TEXT
    )""",
    "classes": """
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        body TEXT NOT NULL,
        fields TEXT,
        methods TEXT,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL
    )""",
    "file_hashes": """
    CREATE TABLE IF NOT EXISTS file_hashes (
        file_path TEXT PRIMARY KEY,
        hash TEXT NOT NULL
    )""",
    "functions_filepath_index": "CREATE INDEX IF NOT EXISTS idx_functions_file_path ON functions(file_path)",
    "classes_filepath_index": "CREATE INDEX IF NOT EXISTS idx_classes_file_path ON classes(file_path)",
}


class CKGDatabase:
    def __init__(self, codebase_path: Path):
        self._db_connection: sqlite3.Connection
        self._codebase_path: Path = codebase_path
        self._parsers: dict[str, Parser] = {}

        if not CKG_DATABASE_PATH.exists():
            CKG_DATABASE_PATH.mkdir(parents=True, exist_ok=True)

        database_path = _get_database_path_for_codebase(codebase_path)
        self._db_connection = sqlite3.connect(database_path)
        self._db_connection.execute("PRAGMA journal_mode=WAL;")
        
        self._create_tables()
        self.sync_codebase()

    def _create_tables(self):
        """Creates all necessary database tables and indices if they don't exist."""
        with self._db_connection:
            for sql in SQL_LIST.values():
                self._db_connection.execute(sql)

    def __del__(self):
        self._db_connection.close()

    def sync_codebase(self):
        """
        Syncs the entire codebase against the index.

        This method scans the filesystem, compares file hashes with the stored ones,
        re-indexes any new or modified files, and removes entries for files that
        have been deleted from the filesystem.
        """
        db_files = {row[0] for row in self._db_connection.execute("SELECT file_path FROM file_hashes").fetchall()}
        disk_files = set()

        for file_path in self._codebase_path.glob("**/*"):
            if file_path.is_file() and self._should_index_file(file_path):
                disk_files.add(file_path.absolute().as_posix())
                
                current_hash = _get_file_content_hash(file_path)
                stored_hash_result = self._db_connection.execute(
                    "SELECT hash FROM file_hashes WHERE file_path = ?", (file_path.absolute().as_posix(),)
                ).fetchone()
                
                stored_hash = stored_hash_result[0] if stored_hash_result else None

                if current_hash != stored_hash:
                    print(f"Re-indexing changed file: {file_path}")
                    self.on_file_changed(file_path)

        # Remove files from index that are no longer on disk
        for deleted_file_path_str in db_files - disk_files:
            print(f"Removing deleted file from index: {deleted_file_path_str}")
            self._remove_file_from_index(deleted_file_path_str)

    def on_file_changed(self, file_path: Path):
        """
        Handles the re-indexing process for a single file that has been changed.

        This is the core of the incremental update strategy. It performs the update
        as a single atomic transaction.

        Args:
            file_path: The path to the file that has changed.
        """
        if not self._should_index_file(file_path):
            return
            
        abs_path_str = file_path.absolute().as_posix()
        
        with self._db_connection:
            # 1. Remove old entries for this file
            self._db_connection.execute("DELETE FROM functions WHERE file_path = ?", (abs_path_str,))
            self._db_connection.execute("DELETE FROM classes WHERE file_path = ?", (abs_path_str,))
            
            # 2. Index the new content
            self._index_file(file_path)
            
            # 3. Update the hash
            new_hash = _get_file_content_hash(file_path)
            self._db_connection.execute(
                "INSERT OR REPLACE INTO file_hashes (file_path, hash) VALUES (?, ?)",
                (abs_path_str, new_hash)
            )

    def _remove_file_from_index(self, file_path_str: str):
        """
        Removes all database entries associated with a specific file.

        Args:
            file_path_str: The absolute path of the file to remove, as a string.
        """
        with self._db_connection:
            self._db_connection.execute("DELETE FROM functions WHERE file_path = ?", (file_path_str,))
            self._db_connection.execute("DELETE FROM classes WHERE file_path = ?", (file_path_str,))
            self._db_connection.execute("DELETE FROM file_hashes WHERE file_path = ?", (file_path_str,))

    def _should_index_file(self, file_path: Path) -> bool:
        """
        Determines if a file should be indexed based on its path and extension.

        Args:
            file_path: The path to the file.

        Returns:
            True if the file should be indexed, False otherwise.
        """
        # Ignore hidden files and files in hidden directories
        if file_path.name.startswith(".") or any(part.startswith('.') for part in file_path.parts):
            return False
        # Ignore files with unknown extensions
        if file_path.suffix not in extension_to_language:
            return False
        return True

    def _get_parser(self, language: str) -> Parser:
        """
        Lazy-loads and retrieves a tree-sitter parser for a given language.

        Args:
            language: The name of the language (e.g., "python").

        Returns:
            A tree-sitter Parser instance for that language.
        """
        if language not in self._parsers:
            parser = get_parser(language)
            self._parsers[language] = parser
        return self._parsers[language]

    def _index_file(self, file_path: Path) -> None:
        """
        Parses a single file and inserts its symbols into the database.

        Args:
            file_path: The path to the file to be indexed.
        """
        language = extension_to_language.get(file_path.suffix)
        if not language:
            return

        parser = self._get_parser(language)
        try:
            tree = parser.parse(file_path.read_bytes())
            root_node = tree.root_node
            abs_path_str = file_path.absolute().as_posix()

            # The recursive visit methods will call _insert_entry, which commits.
            # To make this transactional for the whole file, we wrap it.
            with self._db_connection:
                match language:
                    case "python":
                        self._recursive_visit_python(root_node, abs_path_str)
                    case "java":
                        self._recursive_visit_java(root_node, abs_path_str)
                    case "cpp":
                        self._recursive_visit_cpp(root_node, abs_path_str)
                    case "c":
                        self._recursive_visit_c(root_node, abs_path_str)
                    case "typescript":
                        self._recursive_visit_typescript(root_node, abs_path_str)
                    case "javascript":
                        self._recursive_visit_javascript(root_node, abs_path_str)
        except Exception as e:
            print(f"Failed to parse or index {file_path}: {e}")

    # ... [All _recursive_visit_* methods remain the same] ...
    def _recursive_visit_python(
        self,
        root_node: Node,
        file_path: str,
        parent_class: ClassEntry | None = None,
        parent_function: FunctionEntry | None = None,
    ):
        """Recursively visit the Python AST and insert the entries into the database."""
        if root_node.type == "function_definition":
            function_name_node = root_node.child_by_field_name("name")
            if function_name_node:
                function_entry = FunctionEntry(
                    name=function_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                if parent_function and parent_class:
                    # determine if the function is a method of the class or a function within a function
                    if (
                        parent_function.start_line >= parent_class.start_line
                        and parent_function.end_line <= parent_class.end_line
                    ):
                        function_entry.parent_function = parent_function.name
                    else:
                        function_entry.parent_class = parent_class.name
                elif parent_function:
                    function_entry.parent_function = parent_function.name
                elif parent_class:
                    function_entry.parent_class = parent_class.name
                self._insert_entry(function_entry)
                parent_function = function_entry
        elif root_node.type == "class_definition":
            class_name_node = root_node.child_by_field_name("name")
            if class_name_node:
                class_body_node = root_node.child_by_field_name("body")
                class_methods = ""
                class_entry = ClassEntry(
                    name=class_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                if class_body_node:
                    for child in class_body_node.children:
                        function_definition_node = None
                        if child.type == "decorated_definition":
                            function_definition_node = child.child_by_field_name("definition")
                        elif child.type == "function_definition":
                            function_definition_node = child
                        if function_definition_node:
                            method_name_node = function_definition_node.child_by_field_name("name")
                            if method_name_node:
                                parameters_node = function_definition_node.child_by_field_name(
                                    "parameters"
                                )
                                return_type_node = child.child_by_field_name("return_type")

                                class_method_info = method_name_node.text.decode()
                                if parameters_node:
                                    class_method_info += f"{parameters_node.text.decode()}"
                                if return_type_node:
                                    class_method_info += f" -> {return_type_node.text.decode()}"
                                class_methods += f"- {class_method_info}\n"
                class_entry.methods = class_methods.strip() if class_methods != "" else None
                parent_class = class_entry
                self._insert_entry(class_entry)

        if len(root_node.children) != 0:
            for child in root_node.children:
                self._recursive_visit_python(child, file_path, parent_class, parent_function)

    def _recursive_visit_java(
        self,
        root_node: Node,
        file_path: str,
        parent_class: ClassEntry | None = None,
        parent_function: FunctionEntry | None = None,
    ):
        """Recursively visit the Java AST and insert the entries into the database."""
        if root_node.type == "class_declaration":
            class_name_node = root_node.child_by_field_name("name")
            if class_name_node:
                class_entry = ClassEntry(
                    name=class_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                class_body_node = root_node.child_by_field_name("body")
                class_methods = ""
                class_fields = ""
                if class_body_node:
                    for child in class_body_node.children:
                        if child.type == "field_declaration":
                            class_fields += f"- {child.text.decode()}\n"
                        if child.type == "method_declaration":
                            method_builder = ""
                            for method_property in child.children:
                                if method_property.type == "block":
                                    break
                                method_builder += f"{method_property.text.decode()} "
                            method_builder = method_builder.strip()
                            class_methods += f"- {method_builder}\n"
                class_entry.methods = class_methods.strip() if class_methods != "" else None
                class_entry.fields = class_fields.strip() if class_fields != "" else None
                parent_class = class_entry
                self._insert_entry(class_entry)
        elif root_node.type == "method_declaration":
            method_name_node = root_node.child_by_field_name("name")
            if method_name_node:
                method_entry = FunctionEntry(
                    name=method_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                if parent_class:
                    method_entry.parent_class = parent_class.name
                self._insert_entry(method_entry)

        if len(root_node.children) != 0:
            for child in root_node.children:
                self._recursive_visit_java(child, file_path, parent_class, parent_function)

    def _recursive_visit_cpp(
        self,
        root_node: Node,
        file_path: str,
        parent_class: ClassEntry | None = None,
        parent_function: FunctionEntry | None = None,
    ):
        """Recursively visit the C++ AST and insert the entries into the database."""
        if root_node.type == "class_specifier":
            class_name_node = root_node.child_by_field_name("name")
            if class_name_node:
                class_entry = ClassEntry(
                    name=class_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                class_body_node = root_node.child_by_field_name("body")
                class_methods = ""
                class_fields = ""
                if class_body_node:
                    for child in class_body_node.children:
                        if child.type == "function_definition":
                            method_builder = ""
                            for method_property in child.children:
                                if method_property.type == "compound_statement":
                                    break
                                method_builder += f"{method_property.text.decode()} "
                            method_builder = method_builder.strip()
                            class_methods += f"- {method_builder}\n"
                        if child.type == "field_declaration":
                            child_is_property = True
                            for child_property in child.children:
                                if child_property.type == "function_declarator":
                                    child_is_property = False
                                    break
                            if child_is_property:
                                class_fields += f"- {child.text.decode()}\n"
                            else:
                                class_methods += f"- {child.text.decode()}\n"
                class_entry.methods = class_methods.strip() if class_methods != "" else None
                class_entry.fields = class_fields.strip() if class_fields != "" else None
                parent_class = class_entry
                self._insert_entry(class_entry)
        elif root_node.type == "function_definition":
            function_declarator_node = root_node.child_by_field_name("declarator")
            if function_declarator_node:
                function_name_node = function_declarator_node.child_by_field_name("declarator")
                if function_name_node:
                    function_entry = FunctionEntry(
                        name=function_name_node.text.decode(),
                        file_path=file_path,
                        body=root_node.text.decode(),
                        start_line=root_node.start_point[0] + 1,
                        end_line=root_node.end_point[0] + 1,
                    )
                    if parent_class:
                        function_entry.parent_class = parent_class.name
                    self._insert_entry(function_entry)

        if len(root_node.children) != 0:
            for child in root_node.children:
                self._recursive_visit_cpp(child, file_path, parent_class, parent_function)

    def _recursive_visit_c(
        self,
        root_node: Node,
        file_path: str,
        parent_class: ClassEntry | None = None,
        parent_function: FunctionEntry | None = None,
    ):
        """Recursively visit the C AST and insert the entries into the database."""
        if root_node.type == "function_definition":
            function_declarator_node = root_node.child_by_field_name("declarator")
            if function_declarator_node:
                function_name_node = function_declarator_node.child_by_field_name("declarator")
                if function_name_node:
                    function_entry = FunctionEntry(
                        name=function_name_node.text.decode(),
                        file_path=file_path,
                        body=root_node.text.decode(),
                        start_line=root_node.start_point[0] + 1,
                        end_line=root_node.end_point[0] + 1,
                    )
                    self._insert_entry(function_entry)

        if len(root_node.children) != 0:
            for child in root_node.children:
                self._recursive_visit_c(child, file_path, parent_class, parent_function)

    def _recursive_visit_typescript(
        self,
        root_node: Node,
        file_path: str,
        parent_class: ClassEntry | None = None,
        parent_function: FunctionEntry | None = None,
    ):
        if root_node.type == "class_declaration":
            class_name_node = root_node.child_by_field_name("name")
            if class_name_node:
                class_entry = ClassEntry(
                    name=class_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                methods = ""
                fields = ""
                class_body_node = root_node.child_by_field_name("body")
                if class_body_node:
                    for child in class_body_node.children:
                        if child.type == "method_definition":
                            method_builder = ""
                            for method_property in child.children:
                                if method_property.type == "statement_block":
                                    break
                                method_builder += f"{method_property.text.decode()} "
                            method_builder = method_builder.strip()
                            methods += f"- {method_builder}\n"
                        elif child.type == "public_field_definition":
                            fields += f"- {child.text.decode()}\n"
                class_entry.methods = methods.strip() if methods != "" else None
                class_entry.fields = fields.strip() if fields != "" else None
                parent_class = class_entry
                self._insert_entry(class_entry)
        elif root_node.type == "method_definition":
            method_name_node = root_node.child_by_field_name("name")
            if method_name_node:
                method_entry = FunctionEntry(
                    name=method_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                if parent_class:
                    method_entry.parent_class = parent_class.name
                self._insert_entry(method_entry)

        if len(root_node.children) != 0:
            for child in root_node.children:
                self._recursive_visit_typescript(child, file_path, parent_class, parent_function)

    def _recursive_visit_javascript(
        self,
        root_node: Node,
        file_path: str,
        parent_class: ClassEntry | None = None,
        parent_function: FunctionEntry | None = None,
    ):
        """Recursively visit the JavaScript AST and insert the entries into the database."""
        if root_node.type == "class_declaration":
            class_name_node = root_node.child_by_field_name("name")
            if class_name_node:
                class_entry = ClassEntry(
                    name=class_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                methods = ""
                fields = ""
                class_body_node = root_node.child_by_field_name("body")
                if class_body_node:
                    for child in class_body_node.children:
                        if child.type == "method_definition":
                            method_builder = ""
                            for method_property in child.children:
                                if method_property.type == "statement_block":
                                    break
                                method_builder += f"{method_property.text.decode()} "
                            method_builder = method_builder.strip()
                            methods += f"- {method_builder}\n"
                        elif child.type == "public_field_definition":
                            fields += f"- {child.text.decode()}\n"
                class_entry.methods = methods.strip() if methods != "" else None
                class_entry.fields = fields.strip() if fields != "" else None
                parent_class = class_entry
                self._insert_entry(class_entry)
        elif root_node.type == "method_definition":
            method_name_node = root_node.child_by_field_name("name")
            if method_name_node:
                method_entry = FunctionEntry(
                    name=method_name_node.text.decode(),
                    file_path=file_path,
                    body=root_node.text.decode(),
                    start_line=root_node.start_point[0] + 1,
                    end_line=root_node.end_point[0] + 1,
                )
                if parent_class:
                    method_entry.parent_class = parent_class.name
                self._insert_entry(method_entry)

        if len(root_node.children) != 0:
            for child in root_node.children:
                self._recursive_visit_javascript(child, file_path, parent_class, parent_function)

    def _insert_entry(self, entry: FunctionEntry | ClassEntry) -> None:
        """
        Inserts a single code entry (function or class) into the database.

        This method is designed to be called from within a larger database transaction
        (e.g., the `with self._db_connection:` block in `_index_file`) to ensure
        that all symbols from a single file are added atomically.

        Args:
            entry: The FunctionEntry or ClassEntry object to insert.
        """
        # The self._db_connection.commit() was removed intentionally.
        # Commits are now handled at a higher level (in on_file_changed)
        # to ensure that all changes for a single file are atomic.
        match entry:
            case FunctionEntry():
                self._insert_function(entry)
            case ClassEntry():
                self._insert_class(entry)

    def _insert_function(self, entry: FunctionEntry) -> None:
        """
        Inserts a function entry into the 'functions' table.

        Args:
            entry: The FunctionEntry to insert.
        """
        self._db_connection.execute(
            """
                INSERT INTO functions (name, file_path, body, start_line, end_line, parent_function, parent_class)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.name,
                entry.file_path,
                entry.body,
                entry.start_line,
                entry.end_line,
                entry.parent_function,
                entry.parent_class,
            ),
        )

    def _insert_class(self, entry: ClassEntry) -> None:
        """
        Inserts a class entry into the 'classes' table.

        Args:
            entry: The ClassEntry to insert.
        """
        self._db_connection.execute(
            """
                INSERT INTO classes (name, file_path, body, fields, methods, start_line, end_line)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.name,
                entry.file_path,
                entry.body,
                entry.fields,
                entry.methods,
                entry.start_line,
                entry.end_line,
            ),
        )

    def query_function(
        self, identifier: str, entry_type: Literal["function", "class_method"] = "function"
    ) -> list[FunctionEntry]:
        """
        Searches for functions or methods by name in the database.

        Args:
            identifier: The name of the function or method to search for.
            entry_type: The type of entry to search for ('function' or 'class_method').

        Returns:
            A list of matching FunctionEntry objects.
        """
        cursor = self._db_connection.execute(
            """SELECT name, file_path, body, start_line, end_line, parent_function, parent_class FROM functions WHERE name = ?""",
            (identifier,),
        )
        records = cursor.fetchall()
        function_entries: list[FunctionEntry] = []
        for record in records:
            match entry_type:
                case "function":
                    if record[6] is None:
                        function_entries.append(
                            FunctionEntry(
                                name=record[0],
                                file_path=record[1],
                                body=record[2],
                                start_line=record[3],
                                end_line=record[4],
                                parent_function=record[5],
                                parent_class=record[6],
                            )
                        )
                case "class_method":
                    if record[6] is not None:
                        function_entries.append(
                            FunctionEntry(
                                name=record[0],
                                file_path=record[1],
                                body=record[2],
                                start_line=record[3],
                                end_line=record[4],
                                parent_function=record[5],
                                parent_class=record[6],
                            )
                        )
        return function_entries

    def query_class(self, identifier: str) -> list[ClassEntry]:
        """
        Searches for a class by name in the database.

        Args:
            identifier: The name of the class to search for.

        Returns:
            A list of matching ClassEntry objects.
        """
        cursor = self._db_connection.execute(
            """SELECT name, file_path, body, fields, methods, start_line, end_line FROM classes WHERE name = ?""",
            (identifier,),
        )
        records = cursor.fetchall()
        class_entries: list[ClassEntry] = []
        for record in records:
            class_entries.append(
                ClassEntry(
                    name=record[0],
                    file_path=record[1],
                    body=record[2],
                    fields=record[3],
                    methods=record[4],
                    start_line=record[5],
                    end_line=record[6],
                )
            )
        return class_entries
