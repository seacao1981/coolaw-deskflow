"""Configuration API route."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.api.schemas.models import ConfigResponse, ConfigUpdateRequest
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["config"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state

    return get_app_state()


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get current configuration (sensitive fields redacted)."""
    state = _get_state()
    config = state.config

    has_key = bool(
        config.llm.anthropic_api_key
        or config.llm.openai_api_key
        or config.llm.dashscope_api_key
    )

    # Get the appropriate model based on current provider
    llm_model = config.llm.anthropic_model
    if config.llm.llm_provider.value == "openai":
        llm_model = config.llm.openai_model
    elif config.llm.llm_provider.value == "dashscope":
        llm_model = config.llm.dashscope_model

    return ConfigResponse(
        llm_provider=config.llm.llm_provider.value,
        llm_model=llm_model,
        llm_temperature=config.llm.llm_temperature,
        llm_max_tokens=config.llm.llm_max_tokens,
        has_api_key=has_key,
        openai_base_url=config.llm.openai_base_url,
        server_host=config.server.host,
        server_port=config.server.port,
        memory_cache_size=config.memory.memory_cache_size,
        tool_timeout=config.tools.tool_timeout,
        log_level=config.server.log_level,
    )


@router.post("/config", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """Update configuration (runtime changes, not persisted to .env)."""
    state = _get_state()
    config = state.config

    # Update LLM config if provided
    if request.llm_provider is not None:
        try:
            from deskflow.config import LLMProvider

            config.llm.llm_provider = LLMProvider(request.llm_provider)
        except ValueError as e:
            msg = f"Invalid provider: {request.llm_provider}"
            raise HTTPException(status_code=400, detail=msg) from e

    if request.llm_model is not None:
        # Update the appropriate model based on current provider
        if config.llm.llm_provider.value == "anthropic":
            config.llm.anthropic_model = request.llm_model
        elif config.llm.llm_provider.value == "openai":
            config.llm.openai_model = request.llm_model
        elif config.llm.llm_provider.value == "dashscope":
            config.llm.dashscope_model = request.llm_model

    if request.llm_temperature is not None:
        config.llm.llm_temperature = request.llm_temperature

    if request.llm_max_tokens is not None:
        config.llm.llm_max_tokens = request.llm_max_tokens

    if request.api_key is not None:
        # Update the appropriate API key based on current provider
        if config.llm.llm_provider.value == "anthropic":
            config.llm.anthropic_api_key = request.api_key
        elif config.llm.llm_provider.value == "openai":
            config.llm.openai_api_key = request.api_key
        elif config.llm.llm_provider.value == "dashscope":
            config.llm.dashscope_api_key = request.api_key

    if request.base_url is not None:
        # Base URL only applicable for OpenAI Compatible provider
        config.llm.openai_base_url = request.base_url
        logger.info("config_updated", field="openai_base_url", value=request.base_url)

    # Update system settings if provided
    if request.server_port is not None:
        config.server.port = request.server_port
        logger.info("config_updated", field="server_port", value=request.server_port)

    if request.log_level is not None:
        config.server.log_level = request.log_level
        logger.info("config_updated", field="log_level", value=request.log_level)

    if request.memory_cache_size is not None:
        config.memory.memory_cache_size = request.memory_cache_size
        logger.info("config_updated", field="memory_cache_size", value=request.memory_cache_size)

    if request.tool_timeout is not None:
        config.tools.tool_timeout = request.tool_timeout
        logger.info("config_updated", field="tool_timeout", value=request.tool_timeout)

    # Return updated config
    return await get_config()
