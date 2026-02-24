"""Browser tool - automate web browser interactions using Playwright.

Features:
- Navigate to URLs
- Click elements
- Fill input fields
- Take screenshots
- Extract page content
- Execute JavaScript
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from deskflow.observability.logging import get_logger
from deskflow.tools.base import BaseTool

if TYPE_CHECKING:
    from deskflow.core.models import ToolResult

logger = get_logger(__name__)

# Try to import playwright, mark as unavailable if not installed
try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright_not_installed", message="Install with: pip install playwright")


class BrowserTool(BaseTool):
    """Browser automation tool using Playwright.

    Security features:
    - Headless mode by default
    - Configurable allowed domains
    - Screenshot and content size limits
    - Timeout protection
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: float = 30.0,
        allowed_domains: list[str] | None = None,
    ) -> None:
        self._headless = headless
        self._timeout = timeout
        self._allowed_domains = allowed_domains or []
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Automate web browser interactions using Playwright. "
            "Supports navigation, clicking, typing, screenshots, and content extraction. "
            "Use this for web scraping, form filling, or any browser-based task."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "Action to perform: navigate, click, fill, screenshot, content, evaluate",
                "enum": ["navigate", "click", "fill", "screenshot", "content", "evaluate", "close"],
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for navigate action)",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for click/fill actions",
            },
            "value": {
                "type": "string",
                "description": "Value to fill in input (for fill action)",
            },
            "javascript": {
                "type": "string",
                "description": "JavaScript code to evaluate (for evaluate action)",
            },
            "full_page": {
                "type": "boolean",
                "description": "Capture full page screenshot (default: false)",
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["action"]

    def _validate_url(self, url: str) -> bool:
        """Check if URL is allowed."""
        if not self._allowed_domains:
            return True

        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for allowed in self._allowed_domains:
            if domain.endswith(allowed.lower()):
                return True
        return False

    async def _ensure_browser(self) -> Page:
        """Ensure browser and page are initialized."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed. Install with: pip install playwright")

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(headless=self._headless)

        if self._page is None:
            self._page = await self._browser.new_page()
            self._page.set_default_timeout(int(self._timeout * 1000))

        return self._page

    async def execute(
        self,
        action: str = "",
        url: str | None = None,
        selector: str | None = None,
        value: str | None = None,
        javascript: str | None = None,
        full_page: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a browser action.

        Args:
            action: Action to perform.
            url: URL for navigation.
            selector: CSS selector for element actions.
            value: Value for fill action.
            javascript: JS code for evaluate action.
            full_page: Capture full page screenshot.

        Returns:
            ToolResult with action output.
        """
        if not action:
            return self._error("No action specified")

        try:
            page = await self._ensure_browser()

            if action == "navigate":
                return await self._navigate(page, url or "")
            elif action == "click":
                return await self._click(page, selector or "")
            elif action == "fill":
                return await self._fill(page, selector or "", value or "")
            elif action == "screenshot":
                return await self._screenshot(page, full_page)
            elif action == "content":
                return await self._content(page)
            elif action == "evaluate":
                return await self._evaluate(page, javascript or "")
            elif action == "close":
                return await self._close()
            else:
                return self._error(f"Unknown action: {action}")

        except Exception as e:
            logger.error("browser_action_failed", action=action, error=str(e))
            return self._error(f"Browser action failed: {e}")

    async def _navigate(self, page: Page, url: str) -> ToolResult:
        """Navigate to a URL."""
        if not url:
            return self._error("No URL provided")

        if not self._validate_url(url):
            return self._error(f"URL not allowed: {url}")

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=int(self._timeout * 1000))
            status = response.status if response else "unknown"
            title = await page.title()

            return self._success(
                f"Navigated to {url}\nStatus: {status}\nTitle: {title}",
                url=url,
                status_code=status,
            )
        except Exception as e:
            return self._error(f"Navigation failed: {e}")

    async def _click(self, page: Page, selector: str) -> ToolResult:
        """Click an element."""
        if not selector:
            return self._error("No selector provided")

        try:
            await page.click(selector, timeout=int(self._timeout * 1000))
            await page.wait_for_load_state("domcontentloaded")
            return self._success(f"Clicked: {selector}")
        except Exception as e:
            return self._error(f"Click failed: {e}")

    async def _fill(self, page: Page, selector: str, value: str) -> ToolResult:
        """Fill an input field."""
        if not selector:
            return self._error("No selector provided")

        try:
            await page.fill(selector, value, timeout=int(self._timeout * 1000))
            return self._success(f"Filled '{selector}' with value")
        except Exception as e:
            return self._error(f"Fill failed: {e}")

    async def _screenshot(self, page: Page, full_page: bool) -> ToolResult:
        """Take a screenshot."""
        try:
            screenshot = await page.screenshot(
                full_page=full_page,
                type="png",
            )
            # Return base64 encoded screenshot
            screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")
            return self._success(
                "Screenshot captured",
                screenshot=screenshot_b64[:10000],  # Truncate for response size
                screenshot_size=len(screenshot),
            )
        except Exception as e:
            return self._error(f"Screenshot failed: {e}")

    async def _content(self, page: Page) -> ToolResult:
        """Get page content."""
        try:
            content = await page.content()
            title = await page.title()
            # Truncate large pages
            content = content[:50000]
            return self._success(
                f"Page Title: {title}\n\n{content}",
                content_length=len(content),
            )
        except Exception as e:
            return self._error(f"Get content failed: {e}")

    async def _evaluate(self, page: Page, javascript: str) -> ToolResult:
        """Execute JavaScript."""
        if not javascript:
            return self._error("No JavaScript provided")

        try:
            result = await page.evaluate(javascript)
            return self._success(f"Result: {result}")
        except Exception as e:
            return self._error(f"JavaScript evaluation failed: {e}")

    async def _close(self) -> ToolResult:
        """Close browser."""
        try:
            if self._page:
                await self._page.close()
                self._page = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            return self._success("Browser closed")
        except Exception as e:
            return self._error(f"Close failed: {e}")

    def _success(self, output: str, **kwargs: Any) -> ToolResult:
        """Create success result."""
        from deskflow.core.models import ToolResult

        return ToolResult(
            success=True,
            output=output,
            error=None,
            duration_ms=0,
            tool_call_id="",
            tool_name=self.name,
            metadata=kwargs if kwargs else {},
        )

    def _error(self, message: str, **kwargs: Any) -> ToolResult:
        """Create error result."""
        from deskflow.core.models import ToolResult

        return ToolResult(
            success=False,
            output="",
            error=message,
            duration_ms=0,
            tool_call_id="",
            tool_name=self.name,
            metadata=kwargs if kwargs else {},
        )
