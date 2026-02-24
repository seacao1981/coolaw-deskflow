"""Tests for built-in shell and file tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from deskflow.tools.builtin.shell import BLOCKED_COMMANDS, ShellTool
from deskflow.tools.builtin.file import FileTool


class TestShellTool:
    """Tests for ShellTool."""

    def setup_method(self) -> None:
        self.tool = ShellTool()

    async def test_basic_command(self) -> None:
        result = await self.tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output

    async def test_empty_command(self) -> None:
        result = await self.tool.execute(command="")
        assert result.success is False
        assert "No command" in (result.error or "")

    async def test_no_command(self) -> None:
        result = await self.tool.execute()
        assert result.success is False

    async def test_blocked_command_rm_rf(self) -> None:
        result = await self.tool.execute(command="rm -rf /")
        assert result.success is False
        assert "Blocked" in (result.error or result.output)

    async def test_blocked_command_fork_bomb(self) -> None:
        result = await self.tool.execute(command=":(){:|:&};:")
        assert result.success is False

    async def test_blocked_prefix_mkfs(self) -> None:
        result = await self.tool.execute(command="mkfs.ext4 /dev/sda1")
        assert result.success is False

    async def test_blocked_command_shutdown(self) -> None:
        result = await self.tool.execute(command="shutdown")
        assert result.success is False

    async def test_nonzero_exit_code(self) -> None:
        result = await self.tool.execute(command="false")
        assert result.success is False

    async def test_working_directory(self, temp_dir: Path) -> None:
        result = await self.tool.execute(
            command="pwd",
            working_dir=str(temp_dir),
        )
        assert result.success is True
        assert str(temp_dir) in result.output

    async def test_tool_metadata(self) -> None:
        assert self.tool.name == "shell"
        assert "command" in self.tool.parameters
        assert "command" in self.tool.required_params

    def test_validate_safe_command(self) -> None:
        # Should not raise for safe commands
        self.tool._validate_command("echo hello")
        self.tool._validate_command("ls -la")
        self.tool._validate_command("python --version")

    def test_validate_blocked_commands(self) -> None:
        from deskflow.errors import ToolSecurityError

        with pytest.raises(ToolSecurityError):
            self.tool._validate_command("rm -rf /")

        with pytest.raises(ToolSecurityError):
            self.tool._validate_command("dd if=/dev/zero of=/dev/sda")


class TestFileTool:
    """Tests for FileTool."""

    def setup_method(self) -> None:
        self.tool = FileTool(allowed_paths=[Path("/tmp")])

    async def test_read_file(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        result = await tool.execute(operation="read", path=str(test_file))
        assert result.success is True
        assert "hello world" in result.output

    async def test_read_nonexistent(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        result = await tool.execute(
            operation="read", path=str(temp_dir / "nope.txt")
        )
        assert result.success is False
        assert "not found" in (result.error or result.output).lower()

    async def test_write_file(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        target = temp_dir / "output.txt"

        result = await tool.execute(
            operation="write",
            path=str(target),
            content="written content",
        )
        assert result.success is True
        assert target.read_text() == "written content"

    async def test_list_directory(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        (temp_dir / "file_a.txt").write_text("a", encoding="utf-8")
        (temp_dir / "file_b.txt").write_text("b", encoding="utf-8")

        result = await tool.execute(operation="list", path=str(temp_dir))
        assert result.success is True
        assert "file_a.txt" in result.output
        assert "file_b.txt" in result.output

    async def test_exists_check(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        (temp_dir / "exists.txt").write_text("yes", encoding="utf-8")

        result = await tool.execute(
            operation="exists", path=str(temp_dir / "exists.txt")
        )
        assert result.success is True
        assert "exists" in result.output

    async def test_file_info(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        test_file = temp_dir / "info_test.txt"
        test_file.write_text("some content", encoding="utf-8")

        result = await tool.execute(operation="info", path=str(test_file))
        assert result.success is True
        assert "file" in result.output
        assert "size" in result.output.lower()

    async def test_search(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        sub = temp_dir / "sub"
        sub.mkdir()
        (sub / "a.py").write_text("# a", encoding="utf-8")
        (sub / "b.py").write_text("# b", encoding="utf-8")
        (sub / "c.txt").write_text("c", encoding="utf-8")

        result = await tool.execute(
            operation="search", path=str(temp_dir), pattern="*.py"
        )
        assert result.success is True
        assert "a.py" in result.output

    async def test_path_security(self) -> None:
        tool = FileTool(allowed_paths=[Path("/tmp/safe")])
        result = await tool.execute(
            operation="read", path="/etc/passwd"
        )
        assert result.success is False
        assert "outside" in (result.error or result.output).lower()

    async def test_missing_params(self) -> None:
        result = await self.tool.execute()
        assert result.success is False

    async def test_unknown_operation(self, temp_dir: Path) -> None:
        tool = FileTool(allowed_paths=[temp_dir])
        result = await tool.execute(
            operation="unknown", path=str(temp_dir)
        )
        assert result.success is False
        assert "Unknown" in (result.error or "")

    def test_tool_metadata(self) -> None:
        assert self.tool.name == "file"
        assert "operation" in self.tool.parameters
        assert "operation" in self.tool.required_params
