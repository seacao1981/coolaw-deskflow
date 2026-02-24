"""Tests for core data models."""

from __future__ import annotations

import time

from deskflow.core.models import (
    AgentStatus,
    Conversation,
    MemoryEntry,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
    ToolResult,
)


class TestMessage:
    """Tests for Message model."""

    def test_create_user_message(self) -> None:
        msg = Message(role=Role.USER, content="Hello")
        assert msg.role == Role.USER
        assert msg.content == "Hello"
        assert msg.id is not None
        assert msg.timestamp > 0

    def test_create_assistant_message_with_tool_calls(self) -> None:
        tc = ToolCall(name="shell", arguments={"command": "ls"})
        msg = Message(
            role=Role.ASSISTANT,
            content="Running command...",
            tool_calls=[tc],
        )
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "shell"

    def test_system_message(self) -> None:
        msg = Message(role=Role.SYSTEM, content="You are an assistant.")
        assert msg.role == Role.SYSTEM

    def test_tool_message_with_call_id(self) -> None:
        msg = Message(
            role=Role.TOOL,
            content="output here",
            tool_call_id="tc-123",
        )
        assert msg.tool_call_id == "tc-123"

    def test_message_metadata(self) -> None:
        msg = Message(
            role=Role.USER,
            content="test",
            metadata={"source": "cli"},
        )
        assert msg.metadata["source"] == "cli"

    def test_unique_ids(self) -> None:
        m1 = Message(role=Role.USER, content="a")
        m2 = Message(role=Role.USER, content="b")
        assert m1.id != m2.id


class TestToolCall:
    """Tests for ToolCall model."""

    def test_default_status_is_pending(self) -> None:
        tc = ToolCall(name="shell", arguments={"command": "echo hi"})
        assert tc.status == ToolCallStatus.PENDING

    def test_status_transitions(self) -> None:
        tc = ToolCall(name="shell", arguments={})
        tc.status = ToolCallStatus.RUNNING
        assert tc.status == ToolCallStatus.RUNNING
        tc.status = ToolCallStatus.COMPLETED
        assert tc.status == ToolCallStatus.COMPLETED

    def test_empty_arguments(self) -> None:
        tc = ToolCall(name="test_tool")
        assert tc.arguments == {}


class TestToolResult:
    """Tests for ToolResult model."""

    def test_success_result(self) -> None:
        result = ToolResult(
            tool_call_id="tc-1",
            tool_name="shell",
            success=True,
            output="hello",
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self) -> None:
        result = ToolResult(
            tool_call_id="tc-1",
            tool_name="shell",
            success=False,
            error="command not found",
        )
        assert result.success is False
        assert "command not found" in (result.error or "")

    def test_duration_default(self) -> None:
        result = ToolResult(tool_call_id="tc-1", tool_name="test", success=True)
        assert result.duration_ms == 0.0


class TestConversation:
    """Tests for Conversation model."""

    def test_create_conversation(self) -> None:
        conv = Conversation()
        assert conv.id is not None
        assert len(conv.messages) == 0

    def test_add_message_updates_timestamp(self) -> None:
        conv = Conversation()
        original_updated = conv.updated_at
        time.sleep(0.01)
        msg = Message(role=Role.USER, content="Hello")
        conv.add_message(msg)
        assert len(conv.messages) == 1
        assert conv.updated_at > original_updated

    def test_conversation_with_title(self) -> None:
        conv = Conversation(title="Test Chat")
        assert conv.title == "Test Chat"


class TestMemoryEntry:
    """Tests for MemoryEntry model."""

    def test_create_with_defaults(self) -> None:
        entry = MemoryEntry(content="test content")
        assert entry.memory_type == "episodic"
        assert entry.importance == 0.5
        assert entry.access_count == 0
        assert entry.tags == []

    def test_importance_bounds(self) -> None:
        entry = MemoryEntry(content="test", importance=0.0)
        assert entry.importance == 0.0
        entry = MemoryEntry(content="test", importance=1.0)
        assert entry.importance == 1.0

    def test_tags_and_embedding(self) -> None:
        entry = MemoryEntry(
            content="test",
            tags=["python", "code"],
            embedding=[0.1, 0.2, 0.3],
        )
        assert len(entry.tags) == 2
        assert entry.embedding is not None
        assert len(entry.embedding) == 3


class TestToolDefinition:
    """Tests for ToolDefinition model."""

    def test_basic_definition(self) -> None:
        td = ToolDefinition(name="shell", description="Run commands")
        assert td.name == "shell"
        assert td.parameters == {}
        assert td.required_params == []


class TestAgentStatus:
    """Tests for AgentStatus model."""

    def test_default_values(self) -> None:
        status = AgentStatus()
        assert status.is_online is True
        assert status.is_busy is False
        assert status.current_task is None
        assert status.total_conversations == 0

    def test_busy_status(self) -> None:
        status = AgentStatus(is_busy=True, current_task="processing")
        assert status.is_busy is True
        assert status.current_task == "processing"


class TestStreamChunk:
    """Tests for StreamChunk model."""

    def test_text_chunk(self) -> None:
        chunk = StreamChunk(type="text", content="Hello")
        assert chunk.type == "text"
        assert chunk.content == "Hello"

    def test_done_chunk(self) -> None:
        chunk = StreamChunk(type="done")
        assert chunk.type == "done"
        assert chunk.content == ""

    def test_tool_start_chunk(self) -> None:
        tc = ToolCall(name="shell", arguments={"command": "ls"})
        chunk = StreamChunk(type="tool_start", tool_call=tc)
        assert chunk.tool_call is not None
        assert chunk.tool_call.name == "shell"
