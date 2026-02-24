"""Tests for Anthropic and OpenAI LLM provider adapters.

Uses mocked API clients so no real API keys are needed.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deskflow.core.models import (
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
)


# ---------------------------------------------------------------------------
# Anthropic adapter tests
# ---------------------------------------------------------------------------

class TestAnthropicConvertMessages:
    """Tests for AnthropicAdapter._convert_messages."""

    def _make_adapter(self) -> Any:
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", model="claude-3-haiku")
        return adapter

    def test_system_message_extracted(self) -> None:
        adapter = self._make_adapter()
        msgs = [
            Message(role=Role.SYSTEM, content="You are helpful"),
            Message(role=Role.USER, content="Hi"),
        ]
        system, api_msgs = adapter._convert_messages(msgs)
        assert system == "You are helpful"
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_user_and_assistant_messages(self) -> None:
        adapter = self._make_adapter()
        msgs = [
            Message(role=Role.USER, content="Hello"),
            Message(role=Role.ASSISTANT, content="Hi there!"),
        ]
        system, api_msgs = adapter._convert_messages(msgs)
        assert system is None
        assert len(api_msgs) == 2
        assert api_msgs[0]["content"] == "Hello"
        assert api_msgs[1]["content"] == "Hi there!"

    def test_assistant_with_tool_calls(self) -> None:
        adapter = self._make_adapter()
        tc = ToolCall(id="tc-1", name="shell", arguments={"command": "ls"})
        msgs = [
            Message(
                role=Role.ASSISTANT,
                content="Let me check",
                tool_calls=[tc],
            ),
        ]
        _, api_msgs = adapter._convert_messages(msgs)
        content = api_msgs[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "tool_use"
        assert content[1]["id"] == "tc-1"
        assert content[1]["name"] == "shell"

    def test_tool_result_message(self) -> None:
        adapter = self._make_adapter()
        msgs = [
            Message(
                role=Role.TOOL,
                content="file1.py\nfile2.py",
                tool_call_id="tc-1",
            ),
        ]
        _, api_msgs = adapter._convert_messages(msgs)
        assert api_msgs[0]["role"] == "user"
        assert api_msgs[0]["content"][0]["type"] == "tool_result"
        assert api_msgs[0]["content"][0]["tool_use_id"] == "tc-1"


class TestAnthropicConvertTools:
    """Tests for AnthropicAdapter._convert_tools."""

    def _make_adapter(self) -> Any:
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        return AnthropicAdapter(api_key="test-key", model="claude-3-haiku")

    def test_none_returns_none(self) -> None:
        adapter = self._make_adapter()
        assert adapter._convert_tools(None) is None

    def test_empty_returns_none(self) -> None:
        adapter = self._make_adapter()
        assert adapter._convert_tools([]) is None

    def test_tools_conversion(self) -> None:
        adapter = self._make_adapter()
        tools = [
            ToolDefinition(
                name="shell",
                description="Run commands",
                parameters={"command": {"type": "string"}},
                required_params=["command"],
            ),
        ]
        result = adapter._convert_tools(tools)
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "shell"
        assert result[0]["input_schema"]["type"] == "object"
        assert "command" in result[0]["input_schema"]["properties"]


class TestAnthropicChat:
    """Tests for AnthropicAdapter.chat with mocked client."""

    async def test_successful_chat(self) -> None:
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", model="claude-3-haiku")

        # Mock the response
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello from Claude!"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 20
        mock_response.stop_reason = "end_turn"

        adapter._client = MagicMock()
        adapter._client.messages = MagicMock()
        adapter._client.messages.create = AsyncMock(return_value=mock_response)

        msgs = [Message(role=Role.USER, content="Hello")]
        result = await adapter.chat(msgs)

        assert result.role == Role.ASSISTANT
        assert result.content == "Hello from Claude!"
        assert result.metadata["provider"] == "anthropic"
        assert result.metadata["usage"]["input_tokens"] == 50

    async def test_chat_with_tool_use_response(self) -> None:
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", model="claude-3-haiku")

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Let me run that..."

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_123"
        mock_tool_block.name = "shell"
        mock_tool_block.input = {"command": "ls"}

        mock_response = MagicMock()
        mock_response.content = [mock_text_block, mock_tool_block]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 30
        mock_response.stop_reason = "tool_use"

        adapter._client = MagicMock()
        adapter._client.messages = MagicMock()
        adapter._client.messages.create = AsyncMock(return_value=mock_response)

        msgs = [Message(role=Role.USER, content="List files")]
        result = await adapter.chat(msgs)

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "shell"
        assert result.tool_calls[0].arguments == {"command": "ls"}

    async def test_chat_rate_limit_error(self) -> None:
        import anthropic as anthropic_lib

        from deskflow.errors import LLMRateLimitError
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", model="claude-3-haiku")
        adapter._client = MagicMock()
        adapter._client.messages = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}

        adapter._client.messages.create = AsyncMock(
            side_effect=anthropic_lib.RateLimitError(
                message="Rate limited",
                response=mock_resp,
                body=None,
            )
        )

        with pytest.raises(LLMRateLimitError):
            await adapter.chat([Message(role=Role.USER, content="Hi")])

    async def test_chat_connection_error(self) -> None:
        import anthropic as anthropic_lib

        from deskflow.errors import LLMConnectionError
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", model="claude-3-haiku")
        adapter._client = MagicMock()
        adapter._client.messages = MagicMock()

        adapter._client.messages.create = AsyncMock(
            side_effect=anthropic_lib.APIConnectionError(request=MagicMock())
        )

        with pytest.raises(LLMConnectionError):
            await adapter.chat([Message(role=Role.USER, content="Hi")])

    def test_count_tokens(self) -> None:
        from deskflow.llm.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", model="claude-3-haiku")

        import asyncio

        msgs = [Message(role=Role.USER, content="a" * 400)]
        count = asyncio.get_event_loop().run_until_complete(adapter.count_tokens(msgs))
        assert count == 100  # 400 / 4


# ---------------------------------------------------------------------------
# OpenAI adapter tests
# ---------------------------------------------------------------------------

class TestOpenAIConvertMessages:
    """Tests for OpenAICompatAdapter._convert_messages."""

    def _make_adapter(self) -> Any:
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        return OpenAICompatAdapter(api_key="test-key", model="gpt-4")

    def test_basic_messages(self) -> None:
        adapter = self._make_adapter()
        msgs = [
            Message(role=Role.SYSTEM, content="You are helpful"),
            Message(role=Role.USER, content="Hi"),
        ]
        api_msgs = adapter._convert_messages(msgs)
        assert len(api_msgs) == 2
        assert api_msgs[0]["role"] == "system"
        assert api_msgs[1]["role"] == "user"

    def test_assistant_with_tool_calls(self) -> None:
        adapter = self._make_adapter()
        tc = ToolCall(id="tc-1", name="shell", arguments={"command": "ls"})
        msgs = [
            Message(role=Role.ASSISTANT, content="Let me check", tool_calls=[tc]),
        ]
        api_msgs = adapter._convert_messages(msgs)
        assert "tool_calls" in api_msgs[0]
        assert api_msgs[0]["tool_calls"][0]["type"] == "function"
        assert api_msgs[0]["tool_calls"][0]["function"]["name"] == "shell"

    def test_tool_message(self) -> None:
        adapter = self._make_adapter()
        msgs = [
            Message(role=Role.TOOL, content="output", tool_call_id="tc-1"),
        ]
        api_msgs = adapter._convert_messages(msgs)
        assert api_msgs[0]["tool_call_id"] == "tc-1"


class TestOpenAIConvertTools:
    """Tests for OpenAICompatAdapter._convert_tools."""

    def _make_adapter(self) -> Any:
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        return OpenAICompatAdapter(api_key="test-key", model="gpt-4")

    def test_none_returns_none(self) -> None:
        adapter = self._make_adapter()
        assert adapter._convert_tools(None) is None

    def test_tools_conversion(self) -> None:
        adapter = self._make_adapter()
        tools = [
            ToolDefinition(
                name="shell",
                description="Run commands",
                parameters={"command": {"type": "string"}},
                required_params=["command"],
            ),
        ]
        result = adapter._convert_tools(tools)
        assert result is not None
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "shell"


class TestOpenAIChat:
    """Tests for OpenAICompatAdapter.chat with mocked client."""

    async def test_successful_chat(self) -> None:
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        adapter = OpenAICompatAdapter(api_key="test-key", model="gpt-4")

        mock_message = MagicMock()
        mock_message.content = "Hello from GPT!"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 20

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        adapter._client = MagicMock()
        adapter._client.chat = MagicMock()
        adapter._client.chat.completions = MagicMock()
        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)

        msgs = [Message(role=Role.USER, content="Hello")]
        result = await adapter.chat(msgs)

        assert result.role == Role.ASSISTANT
        assert result.content == "Hello from GPT!"
        assert result.metadata["usage"]["input_tokens"] == 50

    async def test_chat_with_tool_calls_response(self) -> None:
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        adapter = OpenAICompatAdapter(api_key="test-key", model="gpt-4")

        mock_tc = MagicMock()
        mock_tc.id = "call_abc"
        mock_tc.function = MagicMock()
        mock_tc.function.name = "shell"
        mock_tc.function.arguments = '{"command": "ls"}'

        mock_message = MagicMock()
        mock_message.content = "Let me check"
        mock_message.tool_calls = [mock_tc]

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 80
        mock_response.usage.completion_tokens = 15

        adapter._client = MagicMock()
        adapter._client.chat = MagicMock()
        adapter._client.chat.completions = MagicMock()
        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)

        msgs = [Message(role=Role.USER, content="List files")]
        result = await adapter.chat(msgs)

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "shell"
        assert result.tool_calls[0].arguments == {"command": "ls"}

    async def test_chat_rate_limit_error(self) -> None:
        import openai as openai_lib

        from deskflow.errors import LLMRateLimitError
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        adapter = OpenAICompatAdapter(api_key="test-key", model="gpt-4")
        adapter._client = MagicMock()
        adapter._client.chat = MagicMock()
        adapter._client.chat.completions = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        mock_resp.json.return_value = {"error": {"message": "rate limited"}}

        adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai_lib.RateLimitError(
                message="Rate limited",
                response=mock_resp,
                body=None,
            )
        )

        with pytest.raises(LLMRateLimitError):
            await adapter.chat([Message(role=Role.USER, content="Hi")])

    async def test_chat_connection_error(self) -> None:
        import openai as openai_lib

        from deskflow.errors import LLMConnectionError
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        adapter = OpenAICompatAdapter(api_key="test-key", model="gpt-4")
        adapter._client = MagicMock()
        adapter._client.chat = MagicMock()
        adapter._client.chat.completions = MagicMock()

        adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai_lib.APIConnectionError(request=MagicMock())
        )

        with pytest.raises(LLMConnectionError):
            await adapter.chat([Message(role=Role.USER, content="Hi")])

    def test_count_tokens(self) -> None:
        from deskflow.llm.providers.openai_compat import OpenAICompatAdapter

        adapter = OpenAICompatAdapter(api_key="test-key", model="gpt-4")

        import asyncio

        msgs = [Message(role=Role.USER, content="a" * 200)]
        count = asyncio.get_event_loop().run_until_complete(adapter.count_tokens(msgs))
        assert count == 50  # 200 / 4
