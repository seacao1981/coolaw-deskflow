"""Tests for LLM client and adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from deskflow.core.models import Message, Role, ToolDefinition
from deskflow.errors import LLMAllProvidersFailedError, LLMConnectionError
from deskflow.llm.client import LLMClient


def _make_mock_adapter(name: str = "test") -> AsyncMock:
    """Create a mock LLM adapter."""
    adapter = AsyncMock()
    adapter.provider_name = name
    adapter.model_name = f"{name}-model"
    adapter.chat = AsyncMock(
        return_value=Message(
            role=Role.ASSISTANT,
            content=f"response from {name}",
            metadata={},
        )
    )
    adapter.count_tokens = AsyncMock(return_value=100)
    adapter.health_check = AsyncMock(return_value={"status": "ok"})
    return adapter


class TestLLMClient:
    """Tests for LLMClient with mock adapters."""

    async def test_basic_chat(self) -> None:
        adapter = _make_mock_adapter("primary")
        client = LLMClient(primary=adapter)
        messages = [Message(role=Role.USER, content="Hello")]

        response = await client.chat(messages)
        assert response.role == Role.ASSISTANT
        assert "primary" in response.content

    async def test_provider_name(self) -> None:
        adapter = _make_mock_adapter("anthropic")
        client = LLMClient(primary=adapter)
        assert client.provider_name == "anthropic"
        assert client.model_name == "anthropic-model"

    async def test_failover_to_fallback(self) -> None:
        primary = _make_mock_adapter("primary")
        primary.chat = AsyncMock(
            side_effect=LLMConnectionError("primary", "timeout")
        )

        fallback = _make_mock_adapter("fallback")

        client = LLMClient(primary=primary, fallbacks=[fallback])
        messages = [Message(role=Role.USER, content="Hello")]

        response = await client.chat(messages)
        assert "fallback" in response.content

    async def test_all_providers_fail(self) -> None:
        primary = _make_mock_adapter("primary")
        primary.chat = AsyncMock(
            side_effect=LLMConnectionError("primary", "down")
        )

        fallback = _make_mock_adapter("fallback")
        fallback.chat = AsyncMock(
            side_effect=LLMConnectionError("fallback", "also down")
        )

        client = LLMClient(primary=primary, fallbacks=[fallback])
        messages = [Message(role=Role.USER, content="Hello")]

        with pytest.raises(LLMAllProvidersFailedError):
            await client.chat(messages)

    async def test_count_tokens(self) -> None:
        adapter = _make_mock_adapter()
        adapter.count_tokens = AsyncMock(return_value=42)

        client = LLMClient(primary=adapter)
        count = await client.count_tokens([Message(role=Role.USER, content="test")])
        assert count == 42

    async def test_health_check(self) -> None:
        primary = _make_mock_adapter("anthropic")
        fallback = _make_mock_adapter("openai")

        client = LLMClient(primary=primary, fallbacks=[fallback])
        health = await client.health_check()

        assert "anthropic" in health
        assert "openai" in health
