"""Unified LLM client with failover and retry support."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from deskflow.config import AppConfig, LLMProvider
from deskflow.core.models import (
    Message,
    StreamChunk,
    ToolDefinition,
)
from deskflow.core.token_tracking import record_usage
from deskflow.errors import (
    LLMAllProvidersFailedError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)
from deskflow.llm.providers.anthropic import AnthropicAdapter
from deskflow.llm.providers.dashscope import DashScopeAdapter
from deskflow.llm.providers.openai_compat import OpenAICompatAdapter
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from deskflow.llm.adapter import BaseLLMAdapter

logger = get_logger(__name__)


def create_adapter(config: AppConfig) -> BaseLLMAdapter:
    """Create an LLM adapter based on configuration.

    Args:
        config: Application configuration.

    Returns:
        An LLM adapter instance.

    Raises:
        ValueError: If the provider is not supported or API key is missing.
    """
    provider = config.llm.llm_provider

    if provider == LLMProvider.ANTHROPIC:
        if not config.llm.anthropic_api_key:
            raise ValueError("DESKFLOW_ANTHROPIC_API_KEY is required for Anthropic provider")
        return AnthropicAdapter(
            api_key=config.llm.anthropic_api_key,
            model=config.llm.anthropic_model,
        )
    elif provider == LLMProvider.OPENAI:
        if not config.llm.openai_api_key:
            raise ValueError("DESKFLOW_OPENAI_API_KEY is required for OpenAI provider")
        return OpenAICompatAdapter(
            api_key=config.llm.openai_api_key,
            model=config.llm.openai_model,
            base_url=config.llm.openai_base_url,
        )
    elif provider == LLMProvider.DASHSCOPE:
        if not config.llm.dashscope_api_key:
            raise ValueError("DESKFLOW_DASHSCOPE_API_KEY is required for DashScope provider")
        return DashScopeAdapter(
            api_key=config.llm.dashscope_api_key,
            model=config.llm.dashscope_model,
            base_url=config.llm.openai_base_url,  # Use openai_base_url for DashScope custom endpoint
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


class LLMClient:
    """Unified LLM client with failover and retry.

    Tries the primary adapter first. If it fails with a connection or rate limit
    error, falls back to secondary adapters in order.
    """

    def __init__(
        self,
        primary: BaseLLMAdapter,
        fallbacks: list[BaseLLMAdapter] | None = None,
    ) -> None:
        self._primary = primary
        self._fallbacks = fallbacks or []
        self._adapters = [primary, *self._fallbacks]
        self._total_tokens = 0
        self._today_tokens = 0
        self._today_date = date.today()
        self._request_count = 0

    @property
    def provider_name(self) -> str:
        """Return the primary provider name."""
        return self._primary.provider_name

    @property
    def model_name(self) -> str:
        """Return the primary model name."""
        return self._primary.model_name

    @property
    def total_tokens(self) -> int:
        """Return total tokens used."""
        return self._total_tokens

    @property
    def today_tokens(self) -> int:
        """Return tokens used today."""
        self._check_date_reset()
        return self._today_tokens

    @property
    def request_count(self) -> int:
        """Return total request count."""
        self._check_date_reset()
        return self._request_count

    def _check_date_reset(self) -> None:
        """Reset today count if date changed."""
        today = date.today()
        if today != self._today_date:
            self._today_date = today
            self._today_tokens = 0
            self._request_count = 0

    @retry(
        retry=retry_if_exception_type((LLMConnectionError, LLMRateLimitError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _chat_with_retry(
        self,
        adapter: BaseLLMAdapter,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        max_tokens: int,
        temperature: float,
    ) -> Message:
        """Attempt a chat call with retry on transient errors."""
        return await adapter.chat(messages, tools, max_tokens, temperature)

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        conversation_id: str | None = None,
    ) -> Message:
        """Send a chat request with automatic failover.

        Tries each adapter in order until one succeeds.

        Raises:
            LLMAllProvidersFailedError: If all providers fail.
        """
        errors: list[str] = []
        providers: list[str] = []

        for adapter in self._adapters:
            providers.append(adapter.provider_name)
            try:
                result = await self._chat_with_retry(
                    adapter, messages, tools, max_tokens, temperature
                )
                # Record token usage
                input_tokens = await adapter.count_tokens(messages)
                output_tokens = await adapter.count_tokens([result])
                self._total_tokens += input_tokens + output_tokens
                self._today_tokens += input_tokens + output_tokens
                self._request_count += 1
                record_usage(
                    model=adapter.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                return result
            except LLMError as e:
                logger.warning(
                    "llm_provider_failed",
                    provider=adapter.provider_name,
                    error=str(e),
                )
                errors.append(f"{adapter.provider_name}: {e}")
                continue

        raise LLMAllProvidersFailedError(providers, errors)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a response with failover.

        Only retries on the primary adapter failure. Falls back to non-streaming
        chat if streaming fails on all adapters.
        """
        errors: list[str] = []

        for adapter in self._adapters:
            try:
                async for chunk in adapter.stream(
                    messages, tools, max_tokens, temperature
                ):
                    if chunk.type == "error":
                        # Streaming error from adapter, try next
                        errors.append(f"{adapter.provider_name}: {chunk.content}")
                        break
                    yield chunk
                return  # Successfully streamed
            except LLMError as e:
                logger.warning(
                    "llm_stream_failed",
                    provider=adapter.provider_name,
                    error=str(e),
                )
                errors.append(f"{adapter.provider_name}: {e}")
                continue

        # All streaming failed, try non-streaming as last resort
        try:
            result = await self.chat(messages, tools, max_tokens, temperature)
            yield StreamChunk(type="text", content=result.content)
            for tc in result.tool_calls:
                yield StreamChunk(type="tool_end", tool_call=tc)
            yield StreamChunk(type="done")
        except LLMError:
            yield StreamChunk(
                type="error",
                content=f"All providers failed: {'; '.join(errors)}",
            )

    async def count_tokens(self, messages: list[Message]) -> int:
        """Count tokens using primary adapter."""
        return await self._primary.count_tokens(messages)

    async def health_check(self) -> dict[str, Any]:
        """Check health of all configured adapters."""
        results: dict[str, Any] = {}
        for adapter in self._adapters:
            results[adapter.provider_name] = await adapter.health_check()
        return results
