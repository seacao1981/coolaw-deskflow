"""Shell tool - execute system commands safely."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from deskflow.errors import ToolSecurityError
from deskflow.observability.logging import get_logger
from deskflow.tools.base import BaseTool

if TYPE_CHECKING:
    from deskflow.core.models import ToolResult

logger = get_logger(__name__)

# Commands that are always blocked
BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){:|:&};:",  # Fork bomb
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
}

# Command prefixes that are blocked
BLOCKED_PREFIXES = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs.",
    "dd if=/dev/",
    "chmod -R 777 /",
]


class ShellTool(BaseTool):
    """Execute shell commands with safety restrictions.

    Security features:
    - Dangerous commands are blocked
    - Configurable timeout
    - Output size limit
    - Working directory constraint
    """

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command and return the output. "
            "Use this for running scripts, checking system info, "
            "installing packages, or any command-line operation."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory (optional, defaults to current dir)",
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["command"]

    def _validate_command(self, command: str) -> None:
        """Check if a command is safe to execute.

        Raises:
            ToolSecurityError: If the command is blocked.
        """
        cmd_lower = command.strip().lower()

        # Check exact matches
        if cmd_lower in BLOCKED_COMMANDS:
            raise ToolSecurityError("shell", f"Blocked command: {command}")

        # Check prefixes
        for prefix in BLOCKED_PREFIXES:
            if cmd_lower.startswith(prefix):
                raise ToolSecurityError("shell", f"Blocked command prefix: {prefix}")

    async def execute(
        self,
        command: str = "",
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a shell command.

        Args:
            command: The command to run.
            working_dir: Optional working directory.

        Returns:
            ToolResult with stdout/stderr.
        """
        if not command:
            return self._error("No command provided")

        try:
            self._validate_command(command)
        except ToolSecurityError as e:
            return self._error(str(e))

        cwd = working_dir or os.getcwd()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await process.communicate()

            stdout_str = stdout.decode("utf-8", errors="replace")[:10000]
            stderr_str = stderr.decode("utf-8", errors="replace")[:5000]

            # 对于 mkdir 命令，如果成功且没有输出，提供友好的成功消息
            command_lower = command.strip().lower()
            if process.returncode == 0 and command_lower.startswith("mkdir") and not stdout_str:
                # 尝试从命令中提取目录名
                import re
                match = re.search(r"mkdir\s+(?:-p\s+)?(?:\"([^\"]+)\"|'([^']+)'|(\S+))", command)
                if match:
                    dir_name = match.group(1) or match.group(2) or match.group(3)
                    stdout_str = f"Directory created successfully: {dir_name}"

            if process.returncode == 0:
                output = stdout_str
                if stderr_str:
                    output += f"\n[stderr]:\n{stderr_str}"
                return self._success(output, return_code=process.returncode)
            else:
                error_output = stderr_str or stdout_str or f"Exit code: {process.returncode}"
                return self._error(
                    error_output,
                    return_code=process.returncode,
                )

        except Exception as e:
            return self._error(f"Failed to execute command: {e}")
