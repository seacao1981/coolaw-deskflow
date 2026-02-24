"""Tests for DefaultIdentity."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from deskflow.core.identity import DEFAULT_SYSTEM_PROMPT, DefaultIdentity


class TestDefaultIdentity:
    """Tests for DefaultIdentity."""

    def test_default_system_prompt(self) -> None:
        identity = DefaultIdentity()
        prompt = identity.get_system_prompt()
        assert prompt == DEFAULT_SYSTEM_PROMPT
        assert "DeskFlow Agent" in prompt

    def test_cached_system_prompt(self) -> None:
        identity = DefaultIdentity()
        prompt1 = identity.get_system_prompt()
        prompt2 = identity.get_system_prompt()
        assert prompt1 is prompt2  # Same object (cached)

    def test_persona_name(self) -> None:
        identity = DefaultIdentity()
        assert identity.get_persona_name() == "DeskFlow Agent"

    def test_greeting_content(self) -> None:
        identity = DefaultIdentity()
        greeting = identity.get_greeting()
        assert "DeskFlow Agent" in greeting
        assert "self-evolving" in greeting

    @patch("deskflow.core.identity.datetime")
    def test_morning_greeting(self, mock_dt: object) -> None:
        import datetime

        mock_now = datetime.datetime(2024, 1, 1, 8, 0)
        from unittest.mock import MagicMock

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = mock_now
        with patch("deskflow.core.identity.datetime.datetime", mock_datetime):
            identity = DefaultIdentity()
            greeting = identity.get_greeting()
            assert "Good morning" in greeting

    @patch("deskflow.core.identity.datetime")
    def test_afternoon_greeting(self, mock_dt: object) -> None:
        import datetime

        mock_now = datetime.datetime(2024, 1, 1, 14, 0)
        from unittest.mock import MagicMock

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = mock_now
        with patch("deskflow.core.identity.datetime.datetime", mock_datetime):
            identity = DefaultIdentity()
            greeting = identity.get_greeting()
            assert "Good afternoon" in greeting

    def test_load_from_directory(self, temp_dir: Path) -> None:
        soul = temp_dir / "SOUL.md"
        soul.write_text("Be kind and helpful.", encoding="utf-8")

        identity = DefaultIdentity(identity_dir=temp_dir)
        prompt = identity.get_system_prompt()
        assert "Be kind and helpful." in prompt

    def test_load_multiple_files(self, temp_dir: Path) -> None:
        (temp_dir / "SOUL.md").write_text("Soul content", encoding="utf-8")
        (temp_dir / "AGENT.md").write_text("Agent content", encoding="utf-8")
        (temp_dir / "USER.md").write_text("User prefs", encoding="utf-8")

        identity = DefaultIdentity(identity_dir=temp_dir)
        prompt = identity.get_system_prompt()
        assert "Soul content" in prompt
        assert "Agent content" in prompt
        assert "User prefs" in prompt
        # Parts separated by ---
        assert "---" in prompt

    def test_missing_files_use_default(self, temp_dir: Path) -> None:
        # Empty directory - no persona files
        identity = DefaultIdentity(identity_dir=temp_dir)
        prompt = identity.get_system_prompt()
        assert prompt == DEFAULT_SYSTEM_PROMPT

    def test_custom_persona(self, temp_dir: Path) -> None:
        personas_dir = temp_dir / "personas"
        personas_dir.mkdir()
        (personas_dir / "coder.md").write_text(
            "You are a coding expert.", encoding="utf-8"
        )

        identity = DefaultIdentity(identity_dir=temp_dir, persona="coder")
        prompt = identity.get_system_prompt()
        assert "coding expert" in prompt
