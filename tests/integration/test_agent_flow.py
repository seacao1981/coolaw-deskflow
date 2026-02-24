"""Integration tests for Agent flow with mocked LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from deskflow.core.agent import Agent
from deskflow.core.identity import DefaultIdentity
from deskflow.core.models import (
    MemoryEntry,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolResult,
)
from deskflow.core.task_monitor import TaskMonitor
from deskflow.memory.manager import MemoryManager
from deskflow.tools.builtin.shell import ShellTool
from deskflow.tools.registry import ToolRegistry


class TestAgentFlow:
    """Integration tests for the full agent flow."""

    async def test_chat_with_real_memory_and_tools(
        self, temp_db_path: object
    ) -> None:
        """Agent with real memory storage and tool registry (mocked LLM)."""
        from pathlib import Path

        db_path = Path(str(temp_db_path))
        memory = MemoryManager(db_path)
        await memory.initialize()

        tools = ToolRegistry()
        await tools.register(ShellTool())

        brain = AsyncMock()
        brain.chat = AsyncMock(
            return_value=Message(
                role=Role.ASSISTANT,
                content="I can help with that!",
                metadata={"usage": {"input_tokens": 100, "output_tokens": 50}},
            )
        )
        brain.count_tokens = AsyncMock(return_value=100)

        agent = Agent(
            brain=brain,
            memory=memory,
            tools=tools,
            identity=DefaultIdentity(),
        )

        response = await agent.chat("Hello, test!")
        assert response.content == "I can help with that!"

        # Memory should have stored the interaction
        count = await memory.count()
        assert count >= 1

        await memory.close()

    async def test_multi_turn_conversation(
        self, temp_db_path: object
    ) -> None:
        """Multi-turn conversation should maintain context."""
        from pathlib import Path

        db_path = Path(str(temp_db_path))
        memory = MemoryManager(db_path)
        await memory.initialize()

        tools = ToolRegistry()
        brain = AsyncMock()

        responses = [
            Message(role=Role.ASSISTANT, content="Hi!", metadata={"usage": {}}),
            Message(role=Role.ASSISTANT, content="I remember you!", metadata={"usage": {}}),
        ]
        brain.chat = AsyncMock(side_effect=responses)
        brain.count_tokens = AsyncMock(return_value=50)

        agent = Agent(
            brain=brain,
            memory=memory,
            tools=tools,
            identity=DefaultIdentity(),
        )

        r1 = await agent.chat("Hello")
        conv_id = list(agent._conversations.keys())[0]

        r2 = await agent.chat("Remember me?", conversation_id=conv_id)

        conv = agent._conversations[conv_id]
        assert len(conv.messages) == 4  # 2 user + 2 assistant

        await memory.close()

    async def test_tool_use_flow(self, temp_db_path: object) -> None:
        """Agent should execute tools when LLM requests them."""
        from pathlib import Path

        db_path = Path(str(temp_db_path))
        memory = MemoryManager(db_path)
        await memory.initialize()

        tools = ToolRegistry()
        await tools.register(ShellTool())

        brain = AsyncMock()
        # First response requests tool call, second gives final answer
        tool_call = ToolCall(
            id="tc-1",
            name="shell",
            arguments={"command": "echo integration-test"},
        )
        brain.chat = AsyncMock(
            side_effect=[
                Message(
                    role=Role.ASSISTANT,
                    content="Let me run that...",
                    tool_calls=[tool_call],
                    metadata={"usage": {}},
                ),
                Message(
                    role=Role.ASSISTANT,
                    content="The output was: integration-test",
                    metadata={"usage": {}},
                ),
            ]
        )
        brain.count_tokens = AsyncMock(return_value=50)

        agent = Agent(
            brain=brain,
            memory=memory,
            tools=tools,
            identity=DefaultIdentity(),
        )

        response = await agent.chat("Run echo for me")
        assert "integration-test" in response.content
        assert brain.chat.call_count == 2

        await memory.close()
