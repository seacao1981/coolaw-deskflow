"""Tests for ToolRegistry."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from deskflow.core.models import ToolResult
from deskflow.errors import ToolExecutionError, ToolNotFoundError, ToolTimeoutError
from deskflow.tools.base import BaseTool
from deskflow.tools.registry import ToolRegistry


class MockTool(BaseTool):
    """A simple mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for tests"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"input": {"type": "string"}}

    @property
    def required_params(self) -> list[str]:
        return ["input"]

    async def execute(self, input: str = "", **kwargs: Any) -> ToolResult:
        return self._success(f"processed: {input}")


class SlowTool(BaseTool):
    """A tool that takes too long."""

    @property
    def name(self) -> str:
        return "slow_tool"

    @property
    def description(self) -> str:
        return "A slow tool"

    async def execute(self, **kwargs: Any) -> ToolResult:
        await asyncio.sleep(10)
        return self._success("done")


class FailingTool(BaseTool):
    """A tool that always raises."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "A tool that fails"

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("unexpected error")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    async def test_register_and_get(self, tool_registry: ToolRegistry) -> None:
        tool = MockTool()
        await tool_registry.register(tool)

        retrieved = await tool_registry.get_tool("mock_tool")
        assert retrieved.name == "mock_tool"

    async def test_register_duplicate_raises(self, tool_registry: ToolRegistry) -> None:
        tool = MockTool()
        await tool_registry.register(tool)

        with pytest.raises(ValueError, match="already registered"):
            await tool_registry.register(tool)

    async def test_get_nonexistent_raises(self, tool_registry: ToolRegistry) -> None:
        with pytest.raises(ToolNotFoundError, match="magic"):
            await tool_registry.get_tool("magic")

    async def test_execute_tool(self, tool_registry: ToolRegistry) -> None:
        await tool_registry.register(MockTool())

        result = await tool_registry.execute("mock_tool", {"input": "hello"})
        assert result.success is True
        assert "processed: hello" in result.output
        assert result.duration_ms > 0

    async def test_execute_timeout(self, tool_registry: ToolRegistry) -> None:
        await tool_registry.register(SlowTool())

        with pytest.raises(ToolTimeoutError, match="slow_tool"):
            await tool_registry.execute("slow_tool", {}, timeout=0.1)

    async def test_execute_failure(self, tool_registry: ToolRegistry) -> None:
        await tool_registry.register(FailingTool())

        with pytest.raises(ToolExecutionError, match="failing_tool"):
            await tool_registry.execute("failing_tool", {})

    async def test_list_tools(self, tool_registry: ToolRegistry) -> None:
        await tool_registry.register(MockTool())

        definitions = tool_registry.list_tools()
        assert len(definitions) == 1
        assert definitions[0].name == "mock_tool"
        assert definitions[0].description == "A mock tool for tests"

    async def test_unregister(self, tool_registry: ToolRegistry) -> None:
        await tool_registry.register(MockTool())
        assert tool_registry.count == 1

        await tool_registry.unregister("mock_tool")
        assert tool_registry.count == 0

    async def test_get_tool_names(self, tool_registry: ToolRegistry) -> None:
        await tool_registry.register(MockTool())
        names = tool_registry.get_tool_names()
        assert names == ["mock_tool"]

    async def test_count(self, tool_registry: ToolRegistry) -> None:
        assert tool_registry.count == 0
        await tool_registry.register(MockTool())
        assert tool_registry.count == 1


class TestBaseTool:
    """Tests for BaseTool base class."""

    def test_to_definition(self) -> None:
        tool = MockTool()
        defn = tool.to_definition()
        assert defn.name == "mock_tool"
        assert defn.description == "A mock tool for tests"
        assert "input" in defn.parameters
        assert defn.required_params == ["input"]

    def test_success_helper(self) -> None:
        tool = MockTool()
        result = tool._success("output text", key="value")
        assert result.success is True
        assert result.output == "output text"
        assert result.tool_name == "mock_tool"
        assert result.metadata["key"] == "value"

    def test_error_helper(self) -> None:
        tool = MockTool()
        result = tool._error("something broke", code=42)
        assert result.success is False
        assert result.error == "something broke"
        assert result.tool_name == "mock_tool"
        assert result.metadata["code"] == 42
