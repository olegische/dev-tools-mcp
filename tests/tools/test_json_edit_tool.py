#!/usr/bin/env python3
"""
Unit тесты для json_edit_tool.py
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from dev_tools_mcp.tools.json_edit_tool import JSONEditTool
from dev_tools_mcp.models.session import FileSystemState
from dev_tools_mcp.tools.base import ToolCallArguments


class TestJSONEditTool:
    """Тесты для JSONEditTool"""

    @pytest.fixture
    def json_tool(self):
        """Создает экземпляр JSONEditTool"""
        return JSONEditTool()

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
            "operation": "set",
            "file_path": "test.json",
            "json_path": "$.test",
            "value": "new_value",
            "pretty_print": True,
            "_fs_state": mock_fs_state,
        }

    @pytest.mark.asyncio
    async def test_set_json_value_with_git_diff(self, json_tool, mock_fs_state):
        """Тест set с git diff"""
        with patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._load_json_file') as mock_load, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._save_json_file') as mock_save, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._parse_jsonpath') as mock_parse, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock JSON operations
            mock_load.return_value = {"test": "old_value"}
            mock_save.return_value = None
            
            # Mock JSONPath
            mock_jsonpath = MagicMock()
            mock_jsonpath.find.return_value = [MagicMock()]
            mock_jsonpath.update.return_value = {"test": "new_value"}
            mock_parse.return_value = mock_jsonpath
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.json b/test.json\n--- a/test.json\n+++ b/test.json\n@@ -1,3 +1,3 @@\n {\n-  \"test\": \"old_value\"\n+  \"test\": \"new_value\"\n }"
            
            # Execute set
            result = await json_tool._set_json_value(
                Path("/tmp/test_repo/test.json"),
                "$.test",
                "new_value",
                True,
                mock_fs_state
            )
            
            # Verify git diff was called
            # Note: On macOS, /tmp is symlinked to /private/tmp, so we need to be flexible
            assert mock_git_diff.call_count == 1
            call_args = mock_git_diff.call_args[0]
            assert call_args[1] == mock_fs_state  # fs_state should match
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output
            assert "diff --git" in result.output

    @pytest.mark.asyncio
    async def test_set_json_value_without_git_diff(self, json_tool, mock_fs_state):
        """Тест set без git diff"""
        with patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._load_json_file') as mock_load, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._save_json_file') as mock_save, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._parse_jsonpath') as mock_parse, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock JSON operations
            mock_load.return_value = {"test": "old_value"}
            mock_save.return_value = None
            
            # Mock JSONPath
            mock_jsonpath = MagicMock()
            mock_jsonpath.find.return_value = [MagicMock()]
            mock_jsonpath.update.return_value = {"test": "new_value"}
            mock_parse.return_value = mock_jsonpath
            
            # Mock git diff returns None
            mock_git_diff.return_value = None
            
            # Execute set
            result = await json_tool._set_json_value(
                Path("/tmp/test_repo/test.json"),
                "$.test",
                "new_value",
                True,
                mock_fs_state
            )
            
            # Verify git diff was called
            # Note: On macOS, /tmp is symlinked to /private/tmp, so we need to be flexible
            assert mock_git_diff.call_count == 1
            call_args = mock_git_diff.call_args[0]
            assert call_args[1] == mock_fs_state  # fs_state should match
            
            # Verify result does not contain git diff
            assert "Git diff for" not in result.output
            assert "```diff" not in result.output

    @pytest.mark.asyncio
    async def test_add_json_value_with_git_diff(self, json_tool, mock_fs_state):
        """Тест add с git diff"""
        with patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._load_json_file') as mock_load, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._save_json_file') as mock_save, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._parse_jsonpath') as mock_parse, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock JSON operations
            mock_load.return_value = {"items": []}
            mock_save.return_value = None
            
            # Mock JSONPath
            mock_jsonpath = MagicMock()
            mock_jsonpath.left = MagicMock()
            mock_jsonpath.left.find.return_value = [MagicMock(value={"items": []})]
            
            # Create a proper mock for Fields type
            from jsonpath_ng import Fields
            mock_fields = MagicMock(spec=Fields)
            mock_fields.fields = ["new_item"]
            mock_jsonpath.right = mock_fields
            
            mock_parse.return_value = mock_jsonpath
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.json b/test.json\n--- a/test.json\n+++ b/test.json\n@@ -1,3 +1,4 @@\n {\n   \"items\": [\n+    \"new_item\"\n   ]\n }"
            
            # Execute add
            result = await json_tool._add_json_value(
                Path("/tmp/test_repo/test.json"),
                "$.items[0]",
                "new_item",
                True,
                mock_fs_state
            )
            

            
            # Verify git diff was called
            # Note: On macOS, /tmp is symlinked to /private/tmp, so we need to be flexible
            assert mock_git_diff.call_count == 1
            call_args = mock_git_diff.call_args[0]
            assert call_args[1] == mock_fs_state  # fs_state should match
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output

    @pytest.mark.asyncio
    async def test_remove_json_value_with_git_diff(self, json_tool, mock_fs_state):
        """Тест remove с git diff"""
        with patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._load_json_file') as mock_load, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._save_json_file') as mock_save, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._parse_jsonpath') as mock_parse, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock JSON operations
            mock_load.return_value = {"test": "value_to_remove"}
            mock_save.return_value = None
            
            # Mock JSONPath
            mock_jsonpath = MagicMock()
            mock_match = MagicMock()
            mock_match.full_path.left = MagicMock()
            mock_match.full_path.left.find.return_value = [MagicMock(value={"test": "value_to_remove"})]
            mock_match.path = MagicMock()
            mock_match.path.fields = ["test"]
            mock_jsonpath.find.return_value = [mock_match]
            mock_parse.return_value = mock_jsonpath
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.json b/test.json\n--- a/test.json\n+++ b/test.json\n@@ -1,3 +1,1 @@\n {\n-  \"test\": \"value_to_remove\"\n }"
            
            # Execute remove
            result = await json_tool._remove_json_value(
                Path("/tmp/test_repo/test.json"),
                "$.test",
                True,
                mock_fs_state
            )
            
            # Verify git diff was called
            # Note: On macOS, /tmp is symlinked to /private/tmp, so we need to be flexible
            assert mock_git_diff.call_count == 1
            call_args = mock_git_diff.call_args[0]
            assert call_args[1] == mock_fs_state  # fs_state should match
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output

    @pytest.mark.asyncio
    async def test_execute_set_operation(self, json_tool, mock_arguments, mock_fs_state):
        """Тест выполнения операции set через execute"""
        with patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._load_json_file') as mock_load, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._save_json_file') as mock_save, \
             patch('dev_tools_mcp.tools.json_edit_tool.JSONEditTool._parse_jsonpath') as mock_parse, \
             patch('dev_tools_mcp.tools.utils.get_git_diff') as mock_git_diff:
            
            # Mock JSON operations
            mock_load.return_value = {"test": "old_value"}
            mock_save.return_value = None
            
            # Mock JSONPath
            mock_jsonpath = MagicMock()
            mock_jsonpath.find.return_value = [MagicMock()]
            mock_jsonpath.update.return_value = {"test": "new_value"}
            mock_parse.return_value = mock_jsonpath
            
            # Mock git diff
            mock_git_diff.return_value = "diff --git a/test.json b/test.json\n--- a/test.json\n+++ b/test.json\n@@ -1,3 +1,3 @@\n {\n-  \"test\": \"old_value\"\n+  \"test\": \"new_value\"\n }"
            
            # Execute the tool
            result = await json_tool.execute(mock_arguments)
            
            # Verify git diff was called
            # Note: On macOS, /tmp is symlinked to /private/tmp, so we need to be flexible
            assert mock_git_diff.call_count == 1
            call_args = mock_git_diff.call_args[0]
            assert call_args[1] == mock_fs_state  # fs_state should match
            
            # Verify result contains git diff
            assert "Git diff for" in result.output
            assert "```diff" in result.output
