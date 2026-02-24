"""DashScope (Alibaba Cloud Qwen) LLM adapter.

Uses OpenAI-compatible API endpoint provided by DashScope.
"""

from __future__ import annotations

from typing import Any

from deskflow.llm.providers.openai_compat import OpenAICompatAdapter
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class DashScopeAdapter(OpenAICompatAdapter):
    """Adapter for DashScope Qwen models via OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = DASHSCOPE_BASE_URL,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            **kwargs,
        )

    @property
    def provider_name(self) -> str:
        return "DashScope"
