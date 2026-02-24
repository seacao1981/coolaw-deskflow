"""Tests for WebTool and HTML extraction."""

from __future__ import annotations

import pytest

from deskflow.tools.builtin.web import WebTool


class TestWebTool:
    """Tests for WebTool."""

    def test_tool_metadata(self) -> None:
        tool = WebTool()
        assert tool.name == "web"
        assert "url" in tool.required_params
        assert "url" in tool.parameters

    async def test_empty_url(self) -> None:
        tool = WebTool()
        result = await tool.execute(url="")
        assert result.success is False
        assert "No URL" in (result.error or "")

    def test_extract_text_from_html(self) -> None:
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <script>var x = 1;</script>
            <style>.cls { color: red; }</style>
            <h1>Hello World</h1>
            <p>This is a test paragraph.</p>
            <div>Another section</div>
        </body>
        </html>
        """
        text = WebTool._extract_text_from_html(html)
        assert "Hello World" in text
        assert "test paragraph" in text
        assert "Another section" in text
        assert "var x" not in text  # Script removed
        assert "color: red" not in text  # Style removed

    def test_extract_text_html_entities(self) -> None:
        html = "<p>A &amp; B &lt; C &gt; D &quot;E&quot; &#39;F&#39; &nbsp;G</p>"
        text = WebTool._extract_text_from_html(html)
        assert "A & B" in text
        assert "< C" in text
        assert '> D "E"' in text

    def test_extract_text_br_tags(self) -> None:
        html = "line1<br/>line2<br>line3"
        text = WebTool._extract_text_from_html(html)
        assert "line1" in text
        assert "line2" in text
        assert "line3" in text

    def test_extract_text_truncation(self) -> None:
        from deskflow.tools.builtin.web import MAX_RESPONSE_SIZE

        html = "<p>" + "x" * (MAX_RESPONSE_SIZE + 1000) + "</p>"
        text = WebTool._extract_text_from_html(html)
        assert len(text) <= MAX_RESPONSE_SIZE

    async def test_url_auto_prefix(self) -> None:
        """URLs without http:// should get https:// prefix."""
        tool = WebTool()
        # This will fail to connect (no real network),
        # but we just test that it doesn't fail before making the request
        result = await tool.execute(url="example.invalid.test")
        # Should attempt https:// and fail with connection error
        assert result.success is False
        assert "failed" in (result.error or "").lower() or "error" in (result.error or "").lower()

    def test_to_definition(self) -> None:
        tool = WebTool()
        defn = tool.to_definition()
        assert defn.name == "web"
        assert len(defn.parameters) > 0
