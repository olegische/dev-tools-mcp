#!/usr/bin/env python3
"""
Unit тесты для edit_tool.py
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from dev_tools_mcp.tools.edit_tool import TextEditorTool
from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import ToolCallArguments


class TestEditTool:
    """Тесты для TextEditorTool"""

    @pytest.fixture
    def edit_tool(self):
        """Создает экземпляр TextEditorTool"""
        return TextEditorTool()

    @pytest.fixture
    def mock_fs_state(self):
        """Создает mock FileSystemState"""
        state = FileSystemState()
        state.cwd = Path("/tmp/test_repo")
        state.phase = "edit"
        return state

    @pytest.fixture
    def mock_arguments(self, mock_fs_state):
        """Создает mock аргументы для инструмента"""
        return {
            "command": "str_replace",
            "path": "test.txt",
            "old_str": "old content",
            "new_str": "new content",
            "_fs_state": mock_fs_state,
        }

    @pytest.mark.asyncio
    async def test_str_replace_with_git_diff(self, edit_tool, mock_fs_state):
        """Тест str_replace с git diff"""
        with patch('dev_tools_mcp.tools.edit_tool.resolve_path') as mock_resolve, \
             patch('dev_tools_mcp.tools.edit_tool.Path.exists') as mock_exists, \
             patch('dev_tools_mcp.tools.edit_tool.Path.is_dir') as mock_is_dir, \
             patch('dev_tools_mcp.tools.edit_tool.Path.read_text') as mock_read, \
             patch('dev_tools_mcp.tools.edit_tool.Path.write_text') as mock_write, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock resolve_path
            mock_resolve.return_value = Path("/tmp/test_repo/test.txt")
            
            # Mock file operations
            mock_exists.return_value = True
            mock_is_dir.return_value = False
            mock_read.return_value = "old content\nline2\nline3"
            mock_write.return_value = None
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.txt b/test.txt\n--- a/test.txt\n+++ b/test.txt\n@@ -1 +1 @@\n-old content\n+new content"
            
            # Execute str_replace
            result = await edit_tool.str_replace(
                Path("/tmp/test_repo/test.txt"),
                "old content",
                "new content",
                mock_fs_state
            )
            
            # Verify git diff was called
            mock_git_diff.assert_called_once_with("/tmp/test_repo/test.txt", mock_fs_state)
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output
            assert "diff --git" in result.output

    @pytest.mark.asyncio
    async def test_str_replace_without_git_diff(self, edit_tool, mock_fs_state):
        """Тест str_replace без git diff"""
        with patch('dev_tools_mcp.tools.edit_tool.resolve_path') as mock_resolve, \
             patch('dev_tools_mcp.tools.edit_tool.Path.exists') as mock_exists, \
             patch('dev_tools_mcp.tools.edit_tool.Path.is_dir') as mock_is_dir, \
             patch('dev_tools_mcp.tools.edit_tool.Path.read_text') as mock_read, \
             patch('dev_tools_mcp.tools.edit_tool.Path.write_text') as mock_write, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock resolve_path
            mock_resolve.return_value = Path("/tmp/test_repo/test.txt")
            
            # Mock file operations
            mock_exists.return_value = True
            mock_is_dir.return_value = False
            mock_read.return_value = "old content\nline2\nline3"
            mock_write.return_value = None
            
            # Mock git diff returns None
            mock_git_diff.return_value = None
            
            # Execute str_replace
            result = await edit_tool.str_replace(
                Path("/tmp/test_repo/test.txt"),
                "old content",
                "new content",
                mock_fs_state
            )
            
            # Verify git diff was called
            mock_git_diff.assert_called_once_with("/tmp/test_repo/test.txt", mock_fs_state)
            
            # Verify result does not contain git diff
            assert "Git diff for" not in result.output
            assert "```diff" not in result.output

    @pytest.mark.asyncio
    async def test_insert_with_git_diff(self, edit_tool, mock_fs_state):
        """Тест insert с git diff"""
        with patch('dev_tools_mcp.tools.edit_tool.Path.read_text') as mock_read, \
             patch('dev_tools_mcp.tools.edit_tool.Path.write_text') as mock_write, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock file operations
            mock_read.return_value = "line1\nline2\nline3"
            mock_write.return_value = None
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.txt b/test.txt\n--- a/test.txt\n+++ b/test.txt\n@@ -1,3 +1,4 @@\n line1\n+inserted line\n line2\n line3"
            
            # Execute insert
            result = await edit_tool._insert(
                Path("/tmp/test_repo/test.txt"),
                1,
                "inserted line",
                mock_fs_state
            )
            
            # Verify git diff was called
            mock_git_diff.assert_called_once_with("/tmp/test_repo/test.txt", mock_fs_state)
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output

    @pytest.mark.asyncio
    async def test_create_with_git_diff(self, edit_tool, mock_fs_state):
        """Тест create с git diff"""
        with patch('dev_tools_mcp.tools.edit_tool.Path.write_text') as mock_write, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock file operations
            mock_write.return_value = None
            
            # Mock git diff (for new files, this will show the entire file as addition)
            mock_git_diff.return_value = "diff --git a/test.txt b/test.txt\n--- /dev/null\n+++ b/test.txt\n@@ -0,0 +1,1 @@\n+new file content"
            
            # Execute create
            result = await edit_tool._create_handler(
                {"file_text": "new file content"},
                Path("/tmp/test_repo/test.txt"),
                mock_fs_state
            )
            
            # Verify git diff was called
            mock_git_diff.assert_called_once_with("/tmp/test_repo/test.txt", mock_fs_state)
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output

    @pytest.mark.asyncio
    async def test_execute_str_replace_command(self, edit_tool, mock_arguments, mock_fs_state):
        """Тест выполнения команды str_replace через execute"""
        with patch('dev_tools_mcp.tools.edit_tool.resolve_path') as mock_resolve, \
             patch('dev_tools_mcp.tools.edit_tool.Path.exists') as mock_exists, \
             patch('dev_tools_mcp.tools.edit_tool.Path.is_dir') as mock_is_dir, \
             patch('dev_tools_mcp.tools.edit_tool.Path.read_text') as mock_read, \
             patch('dev_tools_mcp.tools.edit_tool.Path.write_text') as mock_write, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock resolve_path
            mock_resolve.return_value = Path("/tmp/test_repo/test.txt")
            
            # Mock file operations
            mock_exists.return_value = True
            mock_is_dir.return_value = False
            mock_read.return_value = "old content\nline2\nline3"
            mock_write.return_value = None
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.txt b/test.txt\n--- a/test.txt\n+++ b/test.txt\n@@ -1 +1 @@\n-old content\n+new content"
            
            # Execute the tool
            result = await edit_tool.execute(mock_arguments)
            
            # Verify git diff was called
            mock_git_diff.assert_called_once_with("/tmp/test_repo/test.txt", mock_fs_state)
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output
