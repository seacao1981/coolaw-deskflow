"""OpenAI-compatible LLM adapter.

Works with OpenAI, Azure OpenAI, and any OpenAI-compatible API.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import openai

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


class OpenAICompatAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key, model, **kwargs)
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    def _convert_messages(
        self, messages: list[Message]
    ) -> list[dict[str, Any]]:
        """Convert internal messages to OpenAI format."""
        api_messages: list[dict[str, Any]] = []

        for msg in messages:
            api_msg: dict[str, Any] = {
                "role": msg.role.value,
                "content": msg.content,
            }

            if msg.role == Role.ASSISTANT and msg.tool_calls:
                api_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.role == Role.TOOL:
                api_msg["tool_call_id"] = msg.tool_call_id or ""

            api_messages.append(api_msg)

        return api_messages

    def _convert_tools(
        self, tools: list[ToolDefinition] | None
    ) -> list[dict[str, Any]] | None:
        """Convert tool definitions to OpenAI function calling format."""
        if not tools:
            return None

        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": tool.required_params,
                    },
                },
            }
            for tool in tools
        ]

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Message:
        """Send a chat request to OpenAI-compatible API."""
        api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            raise LLMRateLimitError("OpenAI") from e
        except openai.BadRequestError as e:
            if "context" in str(e).lower() or "token" in str(e).lower():
                raise LLMContextOverflowError(0, max_tokens) from e
            raise LLMResponseError("OpenAI", str(e)) from e
        except openai.APIConnectionError as e:
            raise LLMConnectionError("OpenAI", str(e)) from e
        except openai.APIError as e:
            raise LLMResponseError("OpenAI", str(e)) from e

        choice = response.choices[0]
        content_text = choice.message.content or ""
        tool_calls: list[ToolCall] = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                    status=ToolCallStatus.PENDING,
                ))

        usage_info: dict[str, int] = {}
        if response.usage:
            usage_info = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        result = Message(
            role=Role.ASSISTANT,
            content=content_text,
            tool_calls=tool_calls,
            metadata={
                "provider": "openai",
                "model": self._model,
                "usage": usage_info,
                "stop_reason": choice.finish_reason,
            },
        )

        logger.info(
            "llm_chat_complete",
            provider="openai",
            model=self._model,
            input_tokens=usage_info.get("input_tokens", 0),
            output_tokens=usage_info.get("output_tokens", 0),
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
        """Stream response from OpenAI-compatible API."""
        api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        logger.info(
            "llm_stream_request",
            model=self._model,
            messages_count=len(messages),
            tools_count=len(api_tools) if api_tools else 0,
        )
        
        # Debug log for message structure
        for i, msg in enumerate(api_messages):
            if "tool_calls" in msg or msg.get("role") == "tool":
                logger.debug(f"message_{i}_debug", role=msg.get("role"), has_tool_calls="tool_calls" in msg, has_tool_call_id="tool_call_id" in msg, content_preview=msg.get("content", "")[:50] if msg.get("content") else "")

        try:
            stream = await self._client.chat.completions.create(**kwargs)

            current_tool_calls: dict[int, dict[str, str]] = {}
            has_content = False

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Text content
                if delta.content:
                    has_content = True
                    logger.debug("llm_stream_text_chunk", content_length=len(delta.content))
                    yield StreamChunk(type="text", content=delta.content)

                # Tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            current_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                current_tool_calls[idx]["name"] = tc_delta.function.name
                                yield StreamChunk(
                                    type="tool_start",
                                    tool_call=ToolCall(
                                        id=current_tool_calls[idx]["id"],
                                        name=tc_delta.function.name,
                                        status=ToolCallStatus.RUNNING,
                                    ),
                                )
                            if tc_delta.function.arguments:
                                current_tool_calls[idx]["arguments"] += (
                                    tc_delta.function.arguments
                                )

                # Finish
                if chunk.choices[0].finish_reason:
                    logger.info(
                        "llm_stream_finish",
                        finish_reason=chunk.choices[0].finish_reason,
                        tool_calls_count=len(current_tool_calls),
                        has_content=has_content,
                    )
                    for _idx, tc_data in current_tool_calls.items():
                        try:
                            args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamChunk(
                            type="tool_end",
                            tool_call=ToolCall(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=args,
                                status=ToolCallStatus.PENDING,
                            ),
                        )

            if not has_content and not current_tool_calls:
                logger.warning("llm_stream_empty_response", model=self._model)

            yield StreamChunk(type="done")

        except openai.RateLimitError:
            logger.error("llm_stream_rate_limited")
            yield StreamChunk(type="error", content="Rate limited by OpenAI")
        except openai.APIConnectionError as e:
            logger.error("llm_stream_connection_error", error=str(e))
            yield StreamChunk(type="error", content=f"Connection error: {e}")
        except openai.APIError as e:
            logger.error("llm_stream_api_error", error=str(e))
            yield StreamChunk(type="error", content=f"API error: {e}")

    async def count_tokens(self, messages: list[Message]) -> int:
        """Estimate token count (~4 chars per token)."""
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4
