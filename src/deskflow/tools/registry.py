"""Tool registry - manages registration and lookup of tools."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from deskflow.errors import ToolExecutionError, ToolNotFoundError, ToolTimeoutError
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.core.models import ToolDefinition, ToolResult
    from deskflow.tools.base import BaseTool

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing and executing tools.

    Implements ToolRegistryProtocol for injection into Agent.
    """

    def __init__(self, default_timeout: float = 30.0) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._default_timeout = default_timeout

    async def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: Tool to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        logger.info("tool_registered", tool_name=tool.name)

    async def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            logger.info("tool_unregistered", tool_name=name)

    async def get_tool(self, name: str) -> BaseTool:
        """Get a tool by name.

        Raises:
            ToolNotFoundError: If tool doesn't exist.
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a tool by name.

        Args:
            name: Tool name.
            arguments: Tool arguments.
            timeout: Execution timeout in seconds (overrides default).

        Returns:
            ToolResult with execution output.

        Raises:
            ToolNotFoundError: If tool doesn't exist.
            ToolTimeoutError: If execution exceeds timeout.
            ToolExecutionError: If execution fails.
        """
        tool = await self.get_tool(name)
        effective_timeout = timeout or self._default_timeout

        start = time.time()
        try:
            result = await asyncio.wait_for(
                tool.execute(**arguments),
                timeout=effective_timeout,
            )
            duration_ms = (time.time() - start) * 1000
            result.duration_ms = duration_ms

            logger.info(
                "tool_executed",
                tool_name=name,
                success=result.success,
                duration_ms=round(duration_ms, 2),
            )
            return result

        except TimeoutError as e:
            raise ToolTimeoutError(name, effective_timeout) from e
        except ToolNotFoundError:
            raise
        except Exception as e:
            raise ToolExecutionError(name, str(e)) from e

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools as definitions."""
        return [tool.to_definition() for tool in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        """Get names of all registered tools."""
        return list(self._tools.keys())

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)
