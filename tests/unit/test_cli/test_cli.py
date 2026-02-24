"""Tests for CLI entry point and commands."""

from __future__ import annotations

import pytest


class TestCLIEntryPoint:
    """Tests for CLI main module."""

    def test_deskflow_module_import(self) -> None:
        """The __main__ module should be importable."""
        import deskflow.__main__  # noqa: F401

    def test_app_attribute_exists(self) -> None:
        """The __main__ module should define a Typer app."""
        from deskflow.__main__ import app

        assert app is not None


class TestCLIInit:
    """Tests for CLI init command."""

    def test_init_module_import(self) -> None:
        from deskflow.cli.init import init_command

        assert callable(init_command)


class TestCLIServe:
    """Tests for CLI serve command."""

    def test_serve_module_import(self) -> None:
        from deskflow.cli.serve import serve_command

        assert callable(serve_command)


class TestCLIStatus:
    """Tests for CLI status command."""

    def test_status_module_import(self) -> None:
        from deskflow.cli.status import status_command

        assert callable(status_command)


class TestCLIConfig:
    """Tests for CLI config command."""

    def test_config_module_import(self) -> None:
        from deskflow.cli.config_cmd import config_app

        assert config_app is not None


class TestCLIChat:
    """Tests for CLI chat command."""

    def test_chat_module_import(self) -> None:
        from deskflow.cli.chat import chat_command

        assert callable(chat_command)
