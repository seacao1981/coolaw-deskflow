"""Core protocol interfaces for DeskFlow.

Uses Python Protocol classes (structural subtyping) for dependency injection.
Any class implementing these methods is automatically compatible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from deskflow.core.models import (
        MemoryEntry,
        Message,
        StreamChunk,
        ToolDefinition,
        ToolResult,
    )


@runtime_checkable
class BrainProtocol(Protocol):
    """Interface for LLM client implementations."""

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Message:
        """Send messages to LLM and get a complete response.

        Args:
            messages: Conversation history.
            tools: Available tool definitions for function calling.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            The assistant's response message.
        """
        ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response chunks from LLM.

        Args:
            messages: Conversation history.
            tools: Available tool definitions for function calling.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Yields:
            StreamChunk objects as they arrive.
        """
        # Make mypy understand this is an async generator
        yield  # type: ignore[misc]
        ...

    async def count_tokens(self, messages: list[Message]) -> int:
        """Estimate token count for a list of messages.

        Args:
            messages: Messages to count tokens for.

        Returns:
            Estimated token count.
        """
        ...


@runtime_checkable
class MemoryProtocol(Protocol):
    """Interface for memory system implementations."""

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry.

        Args:
            entry: The memory entry to store.

        Returns:
            The ID of the stored entry.
        """
        ...

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_type: str | None = None,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories for a query.

        Args:
            query: Search query.
            top_k: Maximum number of results.
            memory_type: Filter by memory type (optional).

        Returns:
            List of relevant memory entries, ranked by relevance.
        """
        ...

    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Get a specific memory entry by ID.

        Args:
            memory_id: The memory ID.

        Returns:
            The memory entry, or None if not found.
        """
        ...

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry.

        Args:
            memory_id: The memory ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def count(self) -> int:
        """Return the total number of stored memories."""
        ...


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Interface for tool registry implementations."""

    async def register(self, tool: Any) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance implementing BaseTool.
        """
        ...

    async def get_tool(self, name: str) -> Any:
        """Get a registered tool by name.

        Args:
            name: Tool name.

        Returns:
            The tool instance.

        Raises:
            ToolNotFoundError: If tool doesn't exist.
        """
        ...

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given arguments.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tool execution result.
        """
        ...

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tool definitions.

        Returns:
            List of tool definitions for LLM function calling.
        """
        ...


@runtime_checkable
class IdentityProtocol(Protocol):
    """Interface for identity/persona system."""

    def get_system_prompt(self) -> str:
        """Get the assembled system prompt including persona definition.

        Returns:
            The complete system prompt string.
        """
        ...

    def get_persona_name(self) -> str:
        """Get the current persona's display name.

        Returns:
            Persona display name.
        """
        ...

    def get_greeting(self) -> str:
        """Get an appropriate greeting message.

        Returns:
            A greeting string, potentially time-aware.
        """
        ...
