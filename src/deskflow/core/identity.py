"""Default identity implementation for DeskFlow.

Provides a system prompt based on persona files (SOUL.md, AGENT.md, USER.md).
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are DeskFlow Agent, an intelligent AI assistant built on the DeskFlow framework.

## Core Principles
- Be helpful, accurate, and concise
- When using tools, explain what you're doing and why
- If a task fails, analyze the error and try a different approach
- Always prioritize user safety and data security
- Be transparent about your limitations

## Capabilities
- Execute shell commands and manage files
- Search the web for information
- Store and recall conversation context
- Learn from interactions to improve over time

## Communication Style
- Professional but friendly
- Use code blocks with syntax highlighting when showing code
- Structure longer responses with headings and lists
- Acknowledge errors honestly and propose solutions
"""


class DefaultIdentity:
    """Default identity implementation using markdown persona files."""

    def __init__(
        self,
        identity_dir: Path | None = None,
        persona: str = "default",
    ) -> None:
        self._identity_dir = identity_dir
        self._persona = persona
        self._system_prompt: str | None = None

    def _load_file(self, filename: str) -> str:
        """Load a persona file from the identity directory."""
        if not self._identity_dir:
            return ""
        filepath = self._identity_dir / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def _build_system_prompt(self) -> str:
        """Build system prompt from persona files."""
        parts: list[str] = []

        # Load SOUL.md (core values and principles)
        soul = self._load_file("SOUL.md")
        if soul:
            parts.append(soul)

        # Load AGENT.md (capabilities and behavior)
        agent = self._load_file("AGENT.md")
        if agent:
            parts.append(agent)

        # Load USER.md (user preferences)
        user = self._load_file("USER.md")
        if user:
            parts.append(user)

        # Load persona-specific file
        if self._persona != "default":
            persona_file = self._load_file(f"personas/{self._persona}.md")
            if persona_file:
                parts.append(persona_file)

        if parts:
            return "\n\n---\n\n".join(parts)

        return DEFAULT_SYSTEM_PROMPT

    def get_system_prompt(self) -> str:
        """Get the assembled system prompt."""
        if self._system_prompt is None:
            self._system_prompt = self._build_system_prompt()
        return self._system_prompt

    def get_persona_name(self) -> str:
        """Get the current persona display name."""
        return "DeskFlow Agent"

    def get_greeting(self) -> str:
        """Get a time-aware greeting message."""
        hour = datetime.datetime.now().hour

        if 5 <= hour < 12:
            time_greeting = "Good morning"
        elif 12 <= hour < 18:
            time_greeting = "Good afternoon"
        elif 18 <= hour < 22:
            time_greeting = "Good evening"
        else:
            time_greeting = "Hello"

        return (
            f"{time_greeting}! I'm DeskFlow Agent, your self-evolving AI assistant. "
            "How can I help you today?"
        )
