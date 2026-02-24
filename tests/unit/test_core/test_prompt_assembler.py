"""Tests for PromptAssembler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from deskflow.core.identity import DefaultIdentity
from deskflow.core.models import MemoryEntry, Message, Role, ToolDefinition
from deskflow.core.prompt_assembler import PromptAssembler


class TestPromptAssembler:
    """Tests for PromptAssembler."""

    def _make_assembler(
        self,
        identity: DefaultIdentity | None = None,
        memory: MagicMock | None = None,
    ) -> PromptAssembler:
        return PromptAssembler(
            identity=identity or DefaultIdentity(),
            memory=memory,
        )

    async def test_basic_assembly(self) -> None:
        assembler = self._make_assembler()
        messages = await assembler.assemble(user_message="Hello")

        assert len(messages) >= 2
        assert messages[0].role == Role.SYSTEM
        assert messages[-1].role == Role.USER
        assert messages[-1].content == "Hello"

    async def test_system_prompt_contains_identity(self) -> None:
        assembler = self._make_assembler()
        messages = await assembler.assemble(user_message="test")
        system_msg = messages[0]
        assert "DeskFlow Agent" in system_msg.content

    async def test_with_memory_context(self) -> None:
        """Test assembling prompt with memory context."""
        mock_memory = MagicMock()
        mock_memory.retrieve = AsyncMock(
            return_value=[
                MemoryEntry(
                    content="User likes Python",
                    memory_type="episodic",
                ),
            ]
        )
        mock_memory.get_recent_entities_context = MagicMock(return_value="")

        assembler = self._make_assembler(memory=mock_memory)
        messages = await assembler.assemble(user_message="Hello")

        system_content = messages[0].content
        assert "Relevant Context from Memory" in system_content
        assert "User likes Python" in system_content

    async def test_with_tools(self) -> None:
        assembler = self._make_assembler()
        tools = [
            ToolDefinition(name="shell", description="Run commands"),
            ToolDefinition(name="file", description="Manage files"),
        ]

        messages = await assembler.assemble(
            user_message="List files",
            tools=tools,
        )

        system_content = messages[0].content
        assert "Available Tools" in system_content
        assert "shell" in system_content
        assert "file" in system_content

    async def test_with_conversation_history(self) -> None:
        assembler = self._make_assembler()
        history = [
            Message(role=Role.USER, content="Hi"),
            Message(role=Role.ASSISTANT, content="Hello!"),
        ]

        messages = await assembler.assemble(
            user_message="How are you?",
            conversation_messages=history,
        )

        # System + history(2) + current user = 4
        assert len(messages) == 4
        assert messages[1].content == "Hi"
        assert messages[2].content == "Hello!"
        assert messages[3].content == "How are you?"

    async def test_token_budget_trimming(self) -> None:
        assembler = PromptAssembler(
            identity=DefaultIdentity(),
            max_context_tokens=500,
            response_reserve_tokens=200,
        )

        # Create long history
        history = [
            Message(role=Role.USER, content="x" * 400)
            for _ in range(10)
        ]

        messages = await assembler.assemble(
            user_message="Current message",
            conversation_messages=history,
        )

        # Should have trimmed some history to stay within budget
        # At minimum: system + user message
        assert len(messages) >= 2
        assert messages[-1].content == "Current message"

    async def test_memory_retrieval_failure_graceful(self) -> None:
        """Test that memory retrieval failures are handled gracefully."""
        mock_memory = MagicMock()
        mock_memory.retrieve = AsyncMock(
            side_effect=Exception("DB error")
        )
        mock_memory.get_recent_entities_context = MagicMock(return_value="")

        assembler = self._make_assembler(memory=mock_memory)
        # Should not raise, just skip memory
        messages = await assembler.assemble(user_message="Hello")
        assert len(messages) >= 2

    def test_estimate_tokens(self) -> None:
        assembler = self._make_assembler()
        # ~4 chars per token
        assert assembler._estimate_tokens("a" * 100) == 25

    def test_format_memories_empty(self) -> None:
        assembler = self._make_assembler()
        assert assembler._format_memories([]) == ""

    def test_format_tools_empty(self) -> None:
        assembler = self._make_assembler()
        assert assembler._format_tools_summary([]) == ""
