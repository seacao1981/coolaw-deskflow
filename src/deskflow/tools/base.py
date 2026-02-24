"""Base tool class and tool result types."""

from __future__ import annotations

import abc
from typing import Any

from deskflow.core.models import ToolDefinition, ToolResult


class BaseTool(abc.ABC):
    """Abstract base class for all tools.

    Every tool must define its name, description, parameters schema,
    and an execute method.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique tool name used for registration and LLM function calling."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema of the tool's parameters.

        Override this to define the parameters your tool accepts.
        Default: empty (no parameters).
        """
        return {}

    @property
    def required_params(self) -> list[str]:
        """List of required parameter names.

        Override this to define which parameters are required.
        """
        return []

    def to_definition(self) -> ToolDefinition:
        """Convert this tool to a ToolDefinition for LLM function calling."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            required_params=self.required_params,
        )

    @abc.abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            **kwargs: Tool-specific arguments.

        Returns:
            ToolResult with success/failure status and output.
        """
        ...

    def _success(self, output: str, **metadata: Any) -> ToolResult:
        """Helper to create a successful ToolResult."""
        return ToolResult(
            tool_call_id="",  # Set by executor
            tool_name=self.name,
            success=True,
            output=output,
            metadata=metadata,
        )

    def _error(self, error: str, **metadata: Any) -> ToolResult:
        """Helper to create a failed ToolResult."""
        return ToolResult(
            tool_call_id="",
            tool_name=self.name,
            success=False,
            error=error,
            metadata=metadata,
        )
