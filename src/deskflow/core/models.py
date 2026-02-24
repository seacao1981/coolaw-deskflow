"""Core data models for DeskFlow.

All models use Pydantic v2 for runtime validation and serialization.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    """Message role in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCallStatus(StrEnum):
    """Status of a tool call execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Message(BaseModel):
    """A single message in a conversation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: Role
    content: str
    timestamp: float = Field(default_factory=time.time)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A request to execute a tool."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING


class ToolResult(BaseModel):
    """Result of a tool execution."""

    tool_call_id: str
    tool_name: str
    success: bool
    output: str = ""
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    """A conversation session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str | None = None
    messages: list[Message] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        """Add a message and update the timestamp."""
        self.messages.append(message)
        self.updated_at = time.time()


class MemoryEntry(BaseModel):
    """A single memory entry stored in the memory system."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    memory_type: str = "episodic"  # episodic, semantic, procedural
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding: list[float] | None = None
    tags: list[str] = Field(default_factory=list)
    source_conversation_id: str | None = None
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    access_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def with_importance(self, importance: float) -> MemoryEntry:
        """Create a copy of this entry with a new importance value.

        Args:
            importance: New importance value (will be clamped to 0.0-1.0)

        Returns:
            A new MemoryEntry instance with updated importance
        """
        return self.model_copy(update={"importance": max(0.0, min(1.0, importance))})


class ToolDefinition(BaseModel):
    """Definition of a tool for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)


class AgentStatus(BaseModel):
    """Current status of the agent."""

    is_online: bool = True
    is_busy: bool = False
    current_task: str | None = None
    uptime_seconds: float = 0.0
    total_conversations: int = 0
    total_tool_calls: int = 0
    total_tokens_used: int = 0
    memory_count: int = 0
    active_tools: int = 0
    available_tools: int = 0
    llm_provider: str = ""
    llm_model: str = ""


class StreamChunk(BaseModel):
    """A chunk of streaming response."""

    type: str  # "conversation_id", "text", "tool_start", "tool_end", "error", "done"
    content: str = ""
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
