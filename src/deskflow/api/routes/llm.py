"""LLM management API routes."""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from deskflow.api.schemas.models import LLMModelsResponse, LLMTestRequest, LLMTestResponse
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm"])


# Common models for different providers
DASHSCOPE_MODELS = [
    "qwen3.5-plus",
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
    "qwen-max-longcontext",
    "qwen-max-2024-09-19",
    "qwen-plus-2024-08-06",
    "qwen-turbo-2024-08-06",
]

OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]

ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]


async def fetch_models_from_api(base_url: str, api_key: str, provider: str) -> list[str] | None:
    """Try to fetch models from the API endpoint."""
    try:
        # Normalize base URL
        base_url = base_url.rstrip("/")

        # Try standard OpenAI-compatible /v1/models endpoint
        models_url = f"{base_url}/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                # OpenAI-compatible format
                if "data" in data:
                    return [m.get("id", "") for m in data["data"] if m.get("id")]
                # Some providers use different formats
                if "models" in data:
                    return [m.get("id", m.get("name", "")) if isinstance(m, dict) else str(m) for m in data["models"]]

        return None
    except Exception as e:
        logger.debug("fetch_models_failed", provider=provider, error=str(e))
        return None


@router.get("/models", response_model=LLMModelsResponse)
async def list_models(
    provider: str = "dashscope",
    base_url: str | None = None,
    api_key: str | None = None,
) -> LLMModelsResponse:
    """List available models for the specified provider."""

    # Use default base URLs if not provided
    if provider == "dashscope" and not base_url:
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    elif provider == "openai" and not base_url:
        base_url = "https://api.openai.com/v1"

    # Try to fetch from API if api_key is provided
    if api_key and base_url:
        models = await fetch_models_from_api(base_url, api_key, provider)
        if models:
            return LLMModelsResponse(
                models=models,
                provider=provider,
                base_url=base_url,
            )

    # Return default models if API fetch failed or no credentials
    default_models = {
        "dashscope": DASHSCOPE_MODELS,
        "openai": OPENAI_MODELS,
        "anthropic": ANTHROPIC_MODELS,
    }

    models = default_models.get(provider, [])

    return LLMModelsResponse(
        models=models,
        provider=provider,
        base_url=base_url,
    )


@router.post("/test", response_model=LLMTestResponse)
async def test_connection(request: LLMTestRequest) -> LLMTestResponse:
    """Test LLM connection with provided credentials."""

    start_time = time.time()

    try:
        # Normalize base URL
        base_url = request.base_url
        if not base_url:
            if request.provider == "dashscope":
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            elif request.provider == "openai":
                base_url = "https://api.openai.com/v1"
            elif request.provider == "anthropic":
                base_url = "https://api.anthropic.com/v1"

        base_url = base_url.rstrip("/")

        async with httpx.AsyncClient(timeout=15.0) as client:
            if request.provider == "anthropic":
                # Anthropic uses a different endpoint
                test_url = f"{base_url}/messages"
                payload = {
                    "model": request.model,
                    "max_tokens": request.max_tokens,
                    "messages": [{"role": "user", "content": "Hello"}],
                }
                headers = {
                    "x-api-key": request.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }
            else:
                # OpenAI-compatible (including DashScope)
                test_url = f"{base_url}/chat/completions"
                payload = {
                    "model": request.model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                }
                headers = {
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json",
                }

            response = await client.post(test_url, json=payload, headers=headers)

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                # Extract model from response if available
                response_model = data.get("model", request.model)

                return LLMTestResponse(
                    success=True,
                    message="Connection successful",
                    model=response_model,
                    provider=request.provider,
                    latency_ms=round(latency_ms, 2),
                )
            else:
                error_msg = response.json().get("error", {}).get("message", str(response.text))
                return LLMTestResponse(
                    success=False,
                    message=f"API Error: {error_msg}",
                    provider=request.provider,
                    latency_ms=round(latency_ms, 2),
                )

    except httpx.TimeoutException:
        return LLMTestResponse(
            success=False,
            message="Connection timeout. Please check your network and base URL.",
            provider=request.provider,
        )
    except httpx.ConnectError as e:
        return LLMTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
            provider=request.provider,
        )
    except Exception as e:
        logger.error("llm_test_failed", provider=request.provider, error=str(e))
        return LLMTestResponse(
            success=False,
            message=f"Error: {str(e)}",
            provider=request.provider,
        )
