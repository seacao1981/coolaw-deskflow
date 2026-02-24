"""Tests for AppState and application factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from deskflow.app import AppState, create_app, get_app_state
from deskflow.config import AppConfig
from deskflow.core.task_monitor import TaskMonitor


class TestAppState:
    """Tests for AppState dataclass."""

    def test_default_state(self) -> None:
        config = AppConfig()
        state = AppState(config=config)
        assert state.agent is None
        assert state.memory is None
        assert state.tools is None
        assert state.llm_client is None
        assert isinstance(state.monitor, TaskMonitor)

    def test_get_app_state_not_initialized(self) -> None:
        import deskflow.app as app_module

        original = app_module._app_state
        app_module._app_state = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                get_app_state()
        finally:
            app_module._app_state = original


class TestCreateApp:
    """Tests for FastAPI app factory."""

    def test_create_app_returns_fastapi(self) -> None:
        app = create_app()
        assert app.title == "Coolaw DeskFlow"
        assert app.version == "0.1.0"

    def test_app_has_routes(self) -> None:
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/chat" in routes
        assert "/api/health" in routes
        assert "/api/config" in routes
