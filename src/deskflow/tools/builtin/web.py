"""Web tool - HTTP requests and web content extraction."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx

from deskflow.observability.logging import get_logger
from deskflow.tools.base import BaseTool

if TYPE_CHECKING:
    from deskflow.core.models import ToolResult

logger = get_logger(__name__)

MAX_RESPONSE_SIZE = 50_000  # 50KB of text
REQUEST_TIMEOUT = 15.0


class WebTool(BaseTool):
    """Make HTTP requests and extract web content.

    Supports:
    - GET/POST requests
    - HTML to text extraction
    - JSON response parsing
    """

    @property
    def name(self) -> str:
        return "web"

    @property
    def description(self) -> str:
        return (
            "Make HTTP requests to URLs. Can fetch web pages, "
            "call APIs, and extract text content from HTML."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "url": {
                "type": "string",
                "description": "The URL to request",
            },
            "method": {
                "type": "string",
                "description": "HTTP method: GET or POST (default: GET)",
                "enum": ["GET", "POST"],
            },
            "body": {
                "type": "string",
                "description": "Request body (for POST, optional)",
            },
            "extract_text": {
                "type": "boolean",
                "description": "Extract readable text from HTML (default: true)",
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["url"]

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        """Simple HTML to text extraction (no external dependency).

        Strips HTML tags and normalizes whitespace.
        """
        # Remove script and style content
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Convert common block elements to newlines
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</(p|div|h[1-6]|li|tr|section|article)>", "\n", html, flags=re.IGNORECASE)

        # Remove remaining tags
        text = re.sub(r"<[^>]+>", "", html)

        # Decode common HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")

        # Normalize whitespace
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)

        return text[:MAX_RESPONSE_SIZE]

    async def execute(
        self,
        url: str = "",
        method: str = "GET",
        body: str | None = None,
        extract_text: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute an HTTP request.

        Args:
            url: Target URL.
            method: HTTP method (GET or POST).
            body: Request body for POST.
            extract_text: Whether to extract text from HTML.

        Returns:
            ToolResult with response content.
        """
        if not url:
            return self._error("No URL provided")

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "DeskFlow/0.1"},
            ) as client:
                if method.upper() == "POST":
                    response = await client.post(url, content=body)
                else:
                    response = await client.get(url)

            status = response.status_code
            content_type = response.headers.get("content-type", "")

            # JSON response
            if "application/json" in content_type:
                try:
                    json_text = response.text[:MAX_RESPONSE_SIZE]
                    return self._success(
                        json_text,
                        status_code=status,
                        content_type="json",
                    )
                except Exception:
                    pass

            # HTML response
            if "text/html" in content_type and extract_text:
                text = self._extract_text_from_html(response.text)
                return self._success(
                    text,
                    status_code=status,
                    content_type="html",
                    original_length=len(response.text),
                )

            # Other text responses
            text = response.text[:MAX_RESPONSE_SIZE]
            return self._success(
                text,
                status_code=status,
                content_type=content_type,
            )

        except httpx.TimeoutException:
            return self._error(f"Request timed out after {REQUEST_TIMEOUT}s: {url}")
        except httpx.ConnectError as e:
            return self._error(f"Connection failed: {e}")
        except Exception as e:
            return self._error(f"Request failed: {e}")
