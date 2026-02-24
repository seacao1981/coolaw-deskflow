"""Abstract base class for LLM provider adapters."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

from deskflow.core.models import (
    Message,
    Role,
    StreamChunk,
    ToolDefinition,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class BaseLLMAdapter(abc.ABC):
    """Abstract base for all LLM provider adapters.

    Each provider (Anthropic, OpenAI, DashScope) must implement this interface.
    """

    def __init__(self, api_key: str, model: str, **kwargs: Any) -> None:
        self._api_key = api_key
        self._model = model
        self._kwargs = kwargs

    @property
    def provider_name(self) -> str:
        """Return the provider name for logging and error messages."""
        return self.__class__.__name__

    @property
    def model_name(self) -> str:
        """Return the current model name."""
        return self._model

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Message:
        """Send a chat completion request and return the full response."""
        ...

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream chat completion response chunks."""
        # Make mypy understand this is an async generator
        yield  # type: ignore[misc]
        ...

    @abc.abstractmethod
    async def count_tokens(self, messages: list[Message]) -> int:
        """Estimate token count for messages."""
        ...

    async def health_check(self) -> bool:
        """Check if the provider is accessible.

        Returns:
            True if the provider responds, False otherwise.
        """
        try:
            test_msg = Message(role=Role.USER, content="ping")
            await self.chat([test_msg], max_tokens=5, temperature=0.0)
            return True
        except Exception:
            return False
