"""Tests for CLI commands using typer.testing.CliRunner."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.exceptions import Exit as ClickExit
from typer.testing import CliRunner

runner = CliRunner()


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_env_file(self, temp_dir: Path) -> None:
        """init should write a .env file and create data directories."""
        from deskflow.cli.init import init_command

        with patch("deskflow.cli.init.Path") as mock_path_cls:
            mock_path_cls.cwd.return_value = temp_dir

            with (
                patch("deskflow.cli.init.Prompt") as mock_prompt,
                patch("deskflow.cli.init.console"),
            ):
                mock_prompt.ask.side_effect = [
                    "anthropic",
                    "sk-test-12345678",
                    "claude-3-5-sonnet-20241022",
                    "8420",
                ]
                init_command()

            env_path = temp_dir / ".env"
            assert env_path.exists()
            content = env_path.read_text()
            assert "DESKFLOW_LLM_PROVIDER=anthropic" in content
            assert "DESKFLOW_ANTHROPIC_API_KEY=sk-test-12345678" in content
            assert "DESKFLOW_PORT=8420" in content

            assert (temp_dir / "data" / "db").is_dir()
            assert (temp_dir / "data" / "logs").is_dir()
            assert (temp_dir / "data" / "cache").is_dir()

    def test_init_openai_provider(self, temp_dir: Path) -> None:
        from deskflow.cli.init import init_command

        with patch("deskflow.cli.init.Path") as mock_path_cls:
            mock_path_cls.cwd.return_value = temp_dir
            with (
                patch("deskflow.cli.init.Prompt") as mock_prompt,
                patch("deskflow.cli.init.console"),
            ):
                mock_prompt.ask.side_effect = [
                    "openai",
                    "sk-openai-key-123",
                    "gpt-4o",
                    "8420",
                ]
                init_command()

            content = (temp_dir / ".env").read_text()
            assert "DESKFLOW_OPENAI_API_KEY=sk-openai-key-123" in content
            assert "DESKFLOW_OPENAI_BASE_URL" in content

    def test_init_dashscope_provider(self, temp_dir: Path) -> None:
        from deskflow.cli.init import init_command

        with patch("deskflow.cli.init.Path") as mock_path_cls:
            mock_path_cls.cwd.return_value = temp_dir
            with (
                patch("deskflow.cli.init.Prompt") as mock_prompt,
                patch("deskflow.cli.init.console"),
            ):
                mock_prompt.ask.side_effect = [
                    "dashscope",
                    "sk-dashscope-key",
                    "qwen-max",
                    "8420",
                ]
                init_command()

            content = (temp_dir / ".env").read_text()
            assert "DESKFLOW_DASHSCOPE_API_KEY=sk-dashscope-key" in content

    def test_init_existing_env_no_overwrite(self, temp_dir: Path) -> None:
        from deskflow.cli.init import init_command

        env_path = temp_dir / ".env"
        env_path.write_text("EXISTING=true")

        with patch("deskflow.cli.init.Path") as mock_path_cls:
            mock_path_cls.cwd.return_value = temp_dir
            with (
                patch("deskflow.cli.init.Confirm") as mock_confirm,
                patch("deskflow.cli.init.console"),
            ):
                mock_confirm.ask.return_value = False
                init_command()

        assert env_path.read_text() == "EXISTING=true"

    def test_init_empty_api_key_exits(self, temp_dir: Path) -> None:
        from deskflow.cli.init import init_command

        with patch("deskflow.cli.init.Path") as mock_path_cls:
            mock_path_cls.cwd.return_value = temp_dir
            with (
                patch("deskflow.cli.init.Prompt") as mock_prompt,
                patch("deskflow.cli.init.console"),
            ):
                mock_prompt.ask.side_effect = [
                    "anthropic",
                    "",  # empty key
                ]
                with pytest.raises((SystemExit, ClickExit)):
                    init_command()


class TestServeCommand:
    """Tests for the serve command."""

    def test_serve_calls_uvicorn(self) -> None:
        from deskflow.cli.serve import serve_command

        mock_uvicorn = MagicMock()
        with (
            patch("deskflow.cli.serve.console"),
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
        ):
            serve_command(host="0.0.0.0", port=9000, reload=True, log_level="debug")

            mock_uvicorn.run.assert_called_once_with(
                "deskflow.app:create_app",
                factory=True,
                host="0.0.0.0",
                port=9000,
                reload=True,
                log_level="debug",
            )


class TestStatusCommand:
    """Tests for the status command."""

    async def test_check_status_connection_error(self) -> None:
        import httpx

        from deskflow.cli.status import _check_status

        with patch("deskflow.cli.status.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            with patch("deskflow.cli.status.console") as mock_console:
                await _check_status("http://127.0.0.1:8420")
                mock_console.print.assert_called()

    async def test_check_status_success(self) -> None:
        from deskflow.cli.status import _check_status

        health_data = {
            "status": "ok",
            "version": "0.1.0",
            "components": {
                "agent": {"status": "ok", "details": {}},
                "memory": {"status": "ok", "details": {"count": 10}},
            },
        }
        status_data = {
            "is_online": True,
            "is_busy": False,
            "llm_provider": "Anthropic",
            "llm_model": "claude-3-haiku",
            "uptime_seconds": 120.0,
            "total_conversations": 5,
            "total_tool_calls": 10,
            "total_tokens_used": 5000,
            "memory_count": 10,
            "active_tools": 3,
            "available_tools": 3,
        }

        with patch("deskflow.cli.status.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            mock_health_resp = MagicMock()
            mock_health_resp.json.return_value = health_data
            mock_status_resp = MagicMock()
            mock_status_resp.json.return_value = status_data
            mock_client.get = AsyncMock(
                side_effect=[mock_health_resp, mock_status_resp]
            )
            mock_client_cls.return_value = mock_client

            with patch("deskflow.cli.status.console") as mock_console:
                await _check_status("http://127.0.0.1:8420")
                assert mock_console.print.call_count >= 3


class TestConfigCommands:
    """Tests for config show and config list."""

    async def test_show_config_connection_error(self) -> None:
        import httpx

        from deskflow.cli.config_cmd import _show_config

        with patch("deskflow.cli.config_cmd.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            with patch("deskflow.cli.config_cmd.console") as mock_console:
                await _show_config("http://127.0.0.1:8420")
                mock_console.print.assert_called()

    async def test_show_config_success(self) -> None:
        from deskflow.cli.config_cmd import _show_config

        config_data = {
            "llm_provider": "anthropic",
            "llm_model": "claude-3-haiku",
            "llm_temperature": 0.7,
            "llm_max_tokens": 4096,
            "has_api_key": True,
            "server_host": "127.0.0.1",
            "server_port": 8420,
            "memory_cache_size": 1000,
            "tool_timeout": 30.0,
        }

        with patch("deskflow.cli.config_cmd.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = config_data
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with patch("deskflow.cli.config_cmd.console") as mock_console:
                await _show_config("http://127.0.0.1:8420")
                mock_console.print.assert_called()

    def test_config_list_no_vars(self) -> None:
        from deskflow.cli.config_cmd import config_list

        env_backup = {
            k: v for k, v in os.environ.items() if k.startswith("DESKFLOW_")
        }
        for k in env_backup:
            del os.environ[k]

        try:
            with patch("deskflow.cli.config_cmd.console") as mock_console:
                config_list()
                mock_console.print.assert_called()
        finally:
            os.environ.update(env_backup)

    def test_config_list_with_vars(self) -> None:
        from deskflow.cli.config_cmd import config_list

        os.environ["DESKFLOW_TEST_VAR"] = "hello"
        os.environ["DESKFLOW_API_KEY"] = "sk-secret-12345678"

        try:
            with patch("deskflow.cli.config_cmd.console") as mock_console:
                config_list()
                mock_console.print.assert_called()
        finally:
            del os.environ["DESKFLOW_TEST_VAR"]
            del os.environ["DESKFLOW_API_KEY"]


class TestChatCommand:
    """Tests for chat command helpers."""

    def test_chat_command_import(self) -> None:
        from deskflow.cli.chat import chat_command

        assert callable(chat_command)

    def test_run_chat_keyboard_interrupt(self) -> None:
        from deskflow.cli.chat import _run_chat

        with (
            patch("deskflow.cli.chat.asyncio") as mock_asyncio,
            patch("deskflow.cli.chat.console"),
        ):
            mock_asyncio.run.side_effect = KeyboardInterrupt()
            _run_chat(None)  # Should not raise
