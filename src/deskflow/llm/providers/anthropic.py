"""Anthropic Claude LLM adapter."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import anthropic

from deskflow.core.models import (
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
)
from deskflow.errors import (
    LLMConnectionError,
    LLMContextOverflowError,
    LLMRateLimitError,
    LLMResponseError,
)
from deskflow.llm.adapter import BaseLLMAdapter
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = get_logger(__name__)


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude models."""

    def __init__(self, api_key: str, model: str, **kwargs: Any) -> None:
        super().__init__(api_key, model, **kwargs)
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert internal messages to Anthropic format.

        Returns:
            Tuple of (system_prompt, messages_list).
        """
        system_prompt: str | None = None
        api_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_prompt = msg.content
                continue

            api_msg: dict[str, Any] = {"role": msg.role.value}

            if msg.role == Role.ASSISTANT and msg.tool_calls:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                api_msg["content"] = content
            elif msg.role == Role.TOOL:
                api_msg["role"] = "user"
                api_msg["content"] = [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content,
                }]
            else:
                api_msg["content"] = msg.content

            api_messages.append(api_msg)

        return system_prompt, api_messages

    def _convert_tools(
        self, tools: list[ToolDefinition] | None
    ) -> list[dict[str, Any]] | None:
        """Convert tool definitions to Anthropic format."""
        if not tools:
            return None

        api_tools: list[dict[str, Any]] = []
        for tool in tools:
            api_tool: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": tool.required_params,
                },
            }
            api_tools.append(api_tool)

        return api_tools

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Message:
        """Send a chat request to Anthropic Claude."""
        system_prompt, api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if api_tools:
            kwargs["tools"] = api_tools

        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            raise LLMRateLimitError("Anthropic") from e
        except anthropic.BadRequestError as e:
            if "context" in str(e).lower() or "token" in str(e).lower():
                raise LLMContextOverflowError(0, max_tokens) from e
            raise LLMResponseError("Anthropic", str(e)) from e
        except anthropic.APIConnectionError as e:
            raise LLMConnectionError("Anthropic", str(e)) from e
        except anthropic.APIError as e:
            raise LLMResponseError("Anthropic", str(e)) from e

        # Parse response
        content_text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input) if isinstance(block.input, dict) else {},
                    status=ToolCallStatus.PENDING,
                ))

        result = Message(
            role=Role.ASSISTANT,
            content=content_text,
            tool_calls=tool_calls,
            metadata={
                "provider": "anthropic",
                "model": self._model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "stop_reason": response.stop_reason,
            },
        )

        logger.info(
            "llm_chat_complete",
            provider="anthropic",
            model=self._model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tool_calls=len(tool_calls),
        )

        return result

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response from Anthropic Claude."""
        system_prompt, api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if api_tools:
            kwargs["tools"] = api_tools

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                current_tool_id: str | None = None
                current_tool_name: str | None = None
                tool_input_json = ""

                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if hasattr(block, "type") and block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            tool_input_json = ""
                            yield StreamChunk(
                                type="tool_start",
                                tool_call=ToolCall(
                                    id=block.id,
                                    name=block.name,
                                    status=ToolCallStatus.RUNNING,
                                ),
                            )
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            yield StreamChunk(type="text", content=delta.text)
                        elif hasattr(delta, "partial_json"):
                            tool_input_json += delta.partial_json
                    elif event.type == "content_block_stop":
                        if current_tool_id and current_tool_name:
                            try:
                                args = json.loads(tool_input_json) if tool_input_json else {}
                            except json.JSONDecodeError:
                                args = {}
                            yield StreamChunk(
                                type="tool_end",
                                tool_call=ToolCall(
                                    id=current_tool_id,
                                    name=current_tool_name,
                                    arguments=args,
                                    status=ToolCallStatus.PENDING,
                                ),
                            )
                            current_tool_id = None
                            current_tool_name = None
                            tool_input_json = ""

                yield StreamChunk(type="done")

        except anthropic.RateLimitError as e:
            yield StreamChunk(type="error", content=f"Rate limited: {e}")
        except anthropic.APIConnectionError as e:
            yield StreamChunk(type="error", content=f"Connection error: {e}")
        except anthropic.APIError as e:
            yield StreamChunk(type="error", content=f"API error: {e}")

    async def count_tokens(self, messages: list[Message]) -> int:
        """Estimate token count using simple heuristic.

        Anthropic doesn't have a public tokenizer, so we estimate ~4 chars per token.
        """
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4
