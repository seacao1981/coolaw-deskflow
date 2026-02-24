"""Integration tests for tool security enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from deskflow.tools.builtin.file import FileTool
from deskflow.tools.builtin.shell import ShellTool
from deskflow.tools.registry import ToolRegistry
from deskflow.errors import ToolNotFoundError


class TestToolSecurity:
    """Integration tests for tool security features."""

    async def test_shell_dangerous_commands_blocked(self) -> None:
        """All dangerous commands should be blocked at validation level."""
        shell = ShellTool()

        dangerous = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs.ext4 /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            ":(){:|:&};:",
            "chmod -R 777 /",
            "shutdown",
            "reboot",
        ]

        for cmd in dangerous:
            # Call execute directly on the tool (bypasses registry timeout)
            result = await shell.execute(command=cmd)
            assert result.success is False, f"Command should be blocked: {cmd}"

    async def test_file_path_traversal_blocked(self, temp_dir: Path) -> None:
        """Path traversal attempts should be blocked."""
        registry = ToolRegistry()
        safe_dir = temp_dir / "safe"
        safe_dir.mkdir()

        await registry.register(FileTool(allowed_paths=[safe_dir]))

        result = await registry.execute("file", {
            "operation": "read",
            "path": "/etc/passwd",
        })
        assert result.success is False
        assert "outside" in (result.error or result.output).lower()

    async def test_file_operations_within_allowed_paths(
        self, temp_dir: Path
    ) -> None:
        """Operations within allowed paths should work."""
        registry = ToolRegistry()
        await registry.register(FileTool(allowed_paths=[temp_dir]))

        write_result = await registry.execute("file", {
            "operation": "write",
            "path": str(temp_dir / "test.txt"),
            "content": "hello world",
        })
        assert write_result.success is True

        read_result = await registry.execute("file", {
            "operation": "read",
            "path": str(temp_dir / "test.txt"),
        })
        assert read_result.success is True
        assert "hello world" in read_result.output

    async def test_unregistered_tool_rejected(self) -> None:
        """Calling an unregistered tool should raise."""
        registry = ToolRegistry()

        with pytest.raises(ToolNotFoundError):
            await registry.execute("nonexistent_tool", {})

    async def test_safe_shell_commands_pass(self) -> None:
        """Safe commands should execute normally."""
        shell = ShellTool()

        safe_commands = [
            "echo hello",
            "date",
            "whoami",
            "python3 --version",
        ]

        for cmd in safe_commands:
            result = await shell.execute(command=cmd)
            assert result.success is True, f"Safe command failed: {cmd}"
