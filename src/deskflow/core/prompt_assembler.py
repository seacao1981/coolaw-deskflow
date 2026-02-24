"""Prompt assembler for building dynamic system prompts.

Assembles context from identity, memory, and tools into a coherent
system prompt while respecting token budget constraints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deskflow.core.models import MemoryEntry, Message, Role, ToolDefinition
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.core.protocols import BrainProtocol, IdentityProtocol, MemoryProtocol

logger = get_logger(__name__)

# Reserve tokens for the response
DEFAULT_RESPONSE_RESERVE = 4096
# Maximum context window (conservative default)
DEFAULT_MAX_CONTEXT = 128000


class PromptAssembler:
    """Builds dynamic system prompts with token budget management.

    Assembles prompts from:
    1. Identity (persona definition)
    2. Relevant memories
    3. Recent entities context (short-term)
    4. Available tools
    5. Current date/time context
    """

    def __init__(
        self,
        identity: IdentityProtocol,
        memory: MemoryProtocol | None = None,
        brain: BrainProtocol | None = None,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT,
        response_reserve_tokens: int = DEFAULT_RESPONSE_RESERVE,
    ) -> None:
        self._identity = identity
        self._memory = memory
        self._brain = brain
        self._max_context = max_context_tokens
        self._response_reserve = response_reserve_tokens

    def _estimate_tokens(self, text: str) -> int:
        """Simple token estimation: ~4 chars per token."""
        return len(text) // 4

    async def _get_relevant_memories(
        self,
        query: str,
        top_k: int = 5,
        conversation_context: str | None = None,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories for the current query.

        Args:
            query: The current user message
            top_k: Number of memories to retrieve
            conversation_context: Recent conversation history for context

        Returns:
            List of relevant memory entries
        """
        if not self._memory:
            return []

        try:
            return await self._memory.retrieve(query, top_k=top_k)
        except Exception as e:
            logger.warning("memory_retrieval_failed", error=str(e))
            return []

    def _format_memories(self, memories: list[MemoryEntry]) -> str:
        """Format memory entries into a context section."""
        if not memories:
            return ""

        lines = ["## Relevant Context from Memory", ""]
        for mem in memories:
            lines.append(f"- [{mem.memory_type}] {mem.content}")
        lines.append("")

        return "\n".join(lines)

    async def _get_recent_entities_context(self) -> str:
        """Get recent entities context for short-term memory.

        This helps the agent understand references like "the folder I just created".

        Returns:
            Formatted recent entities context string
        """
        if not self._memory:
            return ""

        try:
            # Check if memory has recent entities context method
            if hasattr(self._memory, 'get_recent_entities_context'):
                result = self._memory.get_recent_entities_context(limit=5)
                # Handle both sync and async methods
                if hasattr(result, '__await__'):
                    return await result
                return result or ""
        except Exception as e:
            logger.warning("recent_entities_context_failed", error=str(e))

        return ""

    def _format_tools_summary(self, tools: list[ToolDefinition]) -> str:
        """Format a summary of available tools."""
        if not tools:
            return ""

        lines = ["## Available Tools", ""]
        for tool in tools:
            lines.append(f"- **{tool.name}**: {tool.description}")
        lines.append("")

        return "\n".join(lines)

    async def assemble(
        self,
        user_message: str,
        tools: list[ToolDefinition] | None = None,
        conversation_messages: list[Message] | None = None,
        memory_top_k: int = 5,
    ) -> list[Message]:
        """Assemble a complete message list with system prompt.

        Args:
            user_message: The current user message.
            tools: Available tools.
            conversation_messages: Previous conversation history.
            memory_top_k: Number of memories to retrieve.

        Returns:
            Complete message list ready to send to LLM.
        """
        # 1. Build system prompt
        system_parts: list[str] = []

        # Identity / persona
        identity_prompt = self._identity.get_system_prompt()
        system_parts.append(identity_prompt)

        # Recent entities context (SHORT-TERM MEMORY)
        # This is crucial for understanding references like "the folder I just created"
        recent_entities_section = await self._get_recent_entities_context()
        if recent_entities_section:
            system_parts.append(recent_entities_section)

        # Extract recent conversation context for memory retrieval
        recent_context = ""
        if conversation_messages and len(conversation_messages) > 0:
            # Get last 2 messages for context
            recent = conversation_messages[-2:] if len(conversation_messages) >= 2 else conversation_messages
            recent_context = "\n".join(
                f"{msg.role.value}: {msg.content}" for msg in recent
            )

        # Relevant memories (with conversation context)
        memories = await self._get_relevant_memories(
            user_message,
            top_k=memory_top_k,
            conversation_context=recent_context,
        )
        memory_section = self._format_memories(memories)
        if memory_section:
            system_parts.append(memory_section)

        # Tools summary (LLM also gets tool definitions via function calling,
        # but a summary in the system prompt helps with reasoning)
        if tools:
            tools_section = self._format_tools_summary(tools)
            system_parts.append(tools_section)

        system_prompt = "\n".join(system_parts)

        # 2. Budget check: trim conversation if needed
        budget = self._max_context - self._response_reserve
        system_tokens = self._estimate_tokens(system_prompt)
        user_tokens = self._estimate_tokens(user_message)
        remaining = budget - system_tokens - user_tokens

        messages: list[Message] = [
            Message(role=Role.SYSTEM, content=system_prompt),
        ]

        # Add conversation history (newest first, then reverse)
        if conversation_messages:
            history = list(conversation_messages)
            kept: list[Message] = []
            for msg in reversed(history):
                msg_tokens = self._estimate_tokens(msg.content)
                if remaining >= msg_tokens:
                    kept.insert(0, msg)
                    remaining -= msg_tokens
                else:
                    logger.info(
                        "prompt_truncated",
                        dropped_messages=len(history) - len(kept),
                        remaining_budget=remaining,
                    )
                    break
            messages.extend(kept)

        # Add current user message
        messages.append(Message(role=Role.USER, content=user_message))

        total_tokens = self._estimate_tokens(
            " ".join(m.content for m in messages)
        )
        logger.info(
            "prompt_assembled",
            system_tokens=system_tokens,
            history_messages=len(messages) - 2,
            memory_count=len(memories),
            total_estimated_tokens=total_tokens,
        )

        return messages
