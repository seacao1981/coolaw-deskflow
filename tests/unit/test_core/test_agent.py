"""Tests for Agent (central orchestrator)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from deskflow.core.agent import Agent
from deskflow.core.identity import DefaultIdentity
from deskflow.core.models import (
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolResult,
)
from deskflow.core.task_monitor import TaskMonitor


class TestAgent:
    """Tests for Agent."""

    def _make_agent(
        self,
        brain: AsyncMock,
        memory: AsyncMock,
        tools: AsyncMock,
    ) -> Agent:
        return Agent(
            brain=brain,
            memory=memory,
            tools=tools,
            identity=DefaultIdentity(),
            monitor=TaskMonitor(),
        )

    async def test_simple_chat(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        agent = self._make_agent(mock_brain, mock_memory, mock_tools)

        response = await agent.chat("Hello!")
        assert response.role == Role.ASSISTANT
        assert response.content == "Test response"
        mock_brain.chat.assert_called_once()

    async def test_chat_stores_memory(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        agent = self._make_agent(mock_brain, mock_memory, mock_tools)

        await agent.chat("Hello!")
        mock_memory.store.assert_called_once()

    async def test_chat_with_tool_calls(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc-1", name="shell", arguments={"command": "ls"})
        mock_brain.chat = AsyncMock(
            side_effect=[
                Message(
                    role=Role.ASSISTANT,
                    content="Let me check...",
                    tool_calls=[tool_call],
                    metadata={"usage": {}},
                ),
                Message(
                    role=Role.ASSISTANT,
                    content="Here are the files.",
                    metadata={"usage": {}},
                ),
            ]
        )

        mock_tools.execute = AsyncMock(
            return_value=ToolResult(
                tool_call_id="tc-1",
                tool_name="shell",
                success=True,
                output="file1.py\nfile2.py",
            )
        )

        agent = self._make_agent(mock_brain, mock_memory, mock_tools)
        response = await agent.chat("List the files")

        assert response.content == "Here are the files."
        mock_tools.execute.assert_called_once_with("shell", {"command": "ls"})
        assert mock_brain.chat.call_count == 2

    async def test_chat_cancellation_during_processing(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        """Cancel should work when set during the tool loop."""
        agent = self._make_agent(mock_brain, mock_memory, mock_tools)

        tool_call = ToolCall(id="tc-1", name="shell", arguments={"command": "ls"})
        call_count = 0

        async def chat_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Set cancel flag after first LLM call so the next iteration detects it
                agent._cancel_requested = True
                return Message(
                    role=Role.ASSISTANT,
                    content="Running...",
                    tool_calls=[tool_call],
                    metadata={"usage": {}},
                )
            return Message(
                role=Role.ASSISTANT, content="Done", metadata={"usage": {}}
            )

        mock_brain.chat = AsyncMock(side_effect=chat_side_effect)
        mock_tools.execute = AsyncMock(
            return_value=ToolResult(
                tool_call_id="tc-1", tool_name="shell", success=True, output="ok"
            )
        )

        response = await agent.chat("Hello!")
        assert "[Cancelled" in response.content

    async def test_conversation_persistence(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        agent = self._make_agent(mock_brain, mock_memory, mock_tools)

        await agent.chat("Hello!")
        conv_id = list(agent._conversations.keys())[0]

        await agent.chat("Follow up", conversation_id=conv_id)

        conv = agent._conversations[conv_id]
        assert len(conv.messages) == 4

    async def test_stream_chat_basic(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(type="text", content="Hello ")
            yield StreamChunk(type="text", content="world!")
            yield StreamChunk(type="done")

        mock_brain.stream = mock_stream

        agent = self._make_agent(mock_brain, mock_memory, mock_tools)
        chunks = []
        async for chunk in agent.stream_chat("Hi"):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c.type == "text"]
        assert len(text_chunks) == 2
        assert text_chunks[0].content == "Hello "
        assert text_chunks[1].content == "world!"
        assert chunks[-1].type == "done"

    async def test_tool_call_failure_handling(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc-1", name="shell", arguments={"command": "bad"})
        mock_brain.chat = AsyncMock(
            side_effect=[
                Message(
                    role=Role.ASSISTANT,
                    content="Running...",
                    tool_calls=[tool_call],
                    metadata={"usage": {}},
                ),
                Message(
                    role=Role.ASSISTANT,
                    content="Tool failed, but I can help differently.",
                    metadata={"usage": {}},
                ),
            ]
        )

        mock_tools.execute = AsyncMock(
            side_effect=Exception("Permission denied")
        )

        agent = self._make_agent(mock_brain, mock_memory, mock_tools)
        response = await agent.chat("Try something")

        assert response.content == "Tool failed, but I can help differently."

    async def test_monitor_tracking(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        monitor = TaskMonitor()
        agent = Agent(
            brain=mock_brain,
            memory=mock_memory,
            tools=mock_tools,
            identity=DefaultIdentity(),
            monitor=monitor,
        )

        await agent.chat("Hello!")

        status = monitor.get_status()
        assert status.total_conversations >= 1
        assert status.is_busy is False

    async def test_memory_store_failure_graceful(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        mock_memory.store = AsyncMock(side_effect=Exception("DB error"))

        agent = self._make_agent(mock_brain, mock_memory, mock_tools)
        response = await agent.chat("Hello!")
        assert response.content == "Test response"

    async def test_new_conversation_created(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        agent = self._make_agent(mock_brain, mock_memory, mock_tools)
        assert len(agent._conversations) == 0

        await agent.chat("First message")
        assert len(agent._conversations) == 1

    async def test_max_tool_rounds_limit(
        self, mock_brain: AsyncMock, mock_memory: AsyncMock, mock_tools: AsyncMock
    ) -> None:
        """Agent should stop after MAX_TOOL_ROUNDS to prevent infinite loops."""
        from deskflow.core.agent import MAX_TOOL_ROUNDS

        tool_call = ToolCall(id="tc-1", name="shell", arguments={"command": "ls"})
        mock_brain.chat = AsyncMock(
            return_value=Message(
                role=Role.ASSISTANT,
                content="Trying...",
                tool_calls=[tool_call],
                metadata={"usage": {}},
            )
        )
        mock_tools.execute = AsyncMock(
            return_value=ToolResult(
                tool_call_id="tc-1", tool_name="shell", success=True, output="ok"
            )
        )

        agent = self._make_agent(mock_brain, mock_memory, mock_tools)
        response = await agent.chat("Keep trying")

        assert mock_brain.chat.call_count == MAX_TOOL_ROUNDS
