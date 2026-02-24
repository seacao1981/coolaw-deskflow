"""Shared test fixtures and configuration."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from deskflow.core.models import (
    MemoryEntry,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from deskflow.core.identity import DefaultIdentity
from deskflow.core.task_monitor import TaskMonitor
from deskflow.memory.cache import LRUCache
from deskflow.memory.manager import MemoryManager
from deskflow.memory.storage import MemoryStorage
from deskflow.tools.registry import ToolRegistry


@pytest.fixture
def temp_dir():
    """Provide a temporary directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def temp_db_path(temp_dir: Path) -> Path:
    """Provide a temporary database path."""
    return temp_dir / "test.db"


@pytest.fixture
def sample_message() -> Message:
    """Provide a sample user message."""
    return Message(role=Role.USER, content="Hello, DeskFlow!")


@pytest.fixture
def sample_assistant_message() -> Message:
    """Provide a sample assistant message."""
    return Message(role=Role.ASSISTANT, content="Hello! How can I help?")


@pytest.fixture
def sample_tool_call() -> ToolCall:
    """Provide a sample tool call."""
    return ToolCall(
        id="tc-001",
        name="shell",
        arguments={"command": "echo hello"},
    )


@pytest.fixture
def sample_tool_result() -> ToolResult:
    """Provide a sample tool result."""
    return ToolResult(
        tool_call_id="tc-001",
        tool_name="shell",
        success=True,
        output="hello\n",
        duration_ms=15.0,
    )


@pytest.fixture
def sample_memory_entry() -> MemoryEntry:
    """Provide a sample memory entry."""
    return MemoryEntry(
        content="The user prefers dark mode and uses Python.",
        memory_type="episodic",
        importance=0.7,
        tags=["preference", "python"],
    )


@pytest.fixture
def sample_tool_definition() -> ToolDefinition:
    """Provide a sample tool definition."""
    return ToolDefinition(
        name="shell",
        description="Execute shell commands",
        parameters={"command": {"type": "string"}},
        required_params=["command"],
    )


@pytest.fixture
def mock_brain() -> AsyncMock:
    """Provide a mock BrainProtocol."""
    brain = AsyncMock()
    brain.chat = AsyncMock(
        return_value=Message(
            role=Role.ASSISTANT,
            content="Test response",
            metadata={"usage": {"input_tokens": 100, "output_tokens": 50}},
        )
    )
    brain.count_tokens = AsyncMock(return_value=100)
    return brain


@pytest.fixture
def mock_memory() -> MagicMock:
    """Provide a mock MemoryProtocol."""
    memory = MagicMock()
    memory.store = AsyncMock(return_value="mem-001")
    memory.retrieve = AsyncMock(return_value=[])
    memory.get_by_id = AsyncMock(return_value=None)
    memory.delete = AsyncMock(return_value=True)
    memory.count = MagicMock(return_value=0)
    # Use MagicMock for sync method that returns string
    memory.get_recent_entities_context = MagicMock(return_value="")
    return memory


@pytest.fixture
def mock_tools() -> MagicMock:
    """Provide a mock ToolRegistryProtocol."""
    tools = MagicMock()
    tools.list_tools = MagicMock(return_value=[])
    tools.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="tc-001",
            tool_name="shell",
            success=True,
            output="ok",
        )
    )
    return tools


@pytest.fixture
def mock_identity() -> DefaultIdentity:
    """Provide a default identity instance."""
    return DefaultIdentity()


@pytest.fixture
def task_monitor() -> TaskMonitor:
    """Provide a fresh task monitor."""
    return TaskMonitor()


@pytest.fixture
def lru_cache() -> LRUCache:
    """Provide an LRU cache with capacity 5."""
    return LRUCache(capacity=5)


@pytest.fixture
async def memory_storage(temp_db_path: Path) -> MemoryStorage:
    """Provide an initialized memory storage."""
    storage = MemoryStorage(temp_db_path)
    await storage.initialize()
    yield storage  # type: ignore[misc]
    await storage.close()


@pytest.fixture
async def memory_manager(temp_db_path: Path) -> MemoryManager:
    """Provide an initialized memory manager."""
    manager = MemoryManager(temp_db_path)
    await manager.initialize()
    yield manager  # type: ignore[misc]
    await manager.close()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """Provide a fresh tool registry."""
    return ToolRegistry(default_timeout=5.0)
