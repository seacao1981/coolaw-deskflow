"""Tests for desktop control tools."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from deskflow.tools.desktop.controller import (
    DesktopController,
    MouseController,
    KeyboardController,
    ScreenController,
)


class TestDesktopController:
    """Test DesktopController class."""

    def test_init_default(self):
        """Test default initialization."""
        controller = DesktopController()
        assert controller.safety_mode is True
        assert controller.name == "desktop"
        assert "Control mouse, keyboard, and screen" in controller.description

    def test_init_no_safety(self):
        """Test initialization without safety mode."""
        controller = DesktopController(safety_mode=False)
        assert controller.safety_mode is False

    def test_to_definition(self):
        """Test tool definition."""
        controller = DesktopController()
        definition = controller.to_definition()

        assert definition["name"] == "desktop"
        assert "action" in definition["input_schema"]["properties"]
        assert "mouse_move" in definition["input_schema"]["properties"]["action"]["enum"]

    @pytest.mark.asyncio
    async def test_execute_pyautogui_not_available(self):
        """Test execution when pyautogui is not available."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", False):
            controller = DesktopController()
            result = await controller.execute({"action": "mouse_move", "x": 100, "y": 200})

            assert result.success is False
            assert "pyautogui" in result.error

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self):
        """Test unknown action."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui"):
                controller = DesktopController()
                result = await controller.execute({"action": "unknown_action"})

                assert result.success is False
                assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_mouse_move(self):
        """Test mouse move action."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({"action": "mouse_move", "x": 100, "y": 200, "duration": 0.5})

                mock_pyautogui.moveTo.assert_called_once_with(100, 200, duration=0.5)
                assert result.success is True
                assert "100" in result.output and "200" in result.output

    @pytest.mark.asyncio
    async def test_mouse_click_at_position(self):
        """Test mouse click at specific position."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({
                    "action": "mouse_click",
                    "x": 100,
                    "y": 200,
                    "button": "left"
                })

                mock_pyautogui.click.assert_called_once_with(100, 200, button="left")
                assert result.success is True

    @pytest.mark.asyncio
    async def test_mouse_click_current_position(self):
        """Test mouse click at current position."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({"action": "mouse_click", "button": "right"})

                mock_pyautogui.click.assert_called_once_with(button="right")
                assert result.success is True

    @pytest.mark.asyncio
    async def test_mouse_double_click(self):
        """Test mouse double click."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({"action": "mouse_double_click", "x": 100, "y": 200})

                mock_pyautogui.doubleClick.assert_called_once_with(100, 200)
                assert result.success is True

    @pytest.mark.asyncio
    async def test_get_mouse_pos(self):
        """Test getting mouse position."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                mock_pyautogui.position.return_value = (500, 300)

                controller = DesktopController()
                result = await controller.execute({"action": "get_mouse_pos"})

                assert result.success is True
                assert "500" in result.output and "300" in result.output
                assert result.metadata.get("metadata", {}).get("x") == 500
                assert result.metadata.get("metadata", {}).get("y") == 300

    @pytest.mark.asyncio
    async def test_key_press(self):
        """Test key press."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({"action": "key_press", "key": "enter"})

                mock_pyautogui.press.assert_called_once_with("enter")
                assert result.success is True

    @pytest.mark.asyncio
    async def test_key_combination(self):
        """Test key combination."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({"action": "key_combination", "keys": "ctrl+c"})

                mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")
                assert result.success is True

    @pytest.mark.asyncio
    async def test_type_text(self):
        """Test typing text."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                controller = DesktopController()
                result = await controller.execute({
                    "action": "type_text",
                    "text": "Hello World",
                    "interval": 0.1
                })

                mock_pyautogui.write.assert_called_once_with("Hello World", interval=0.1)
                assert result.success is True

    @pytest.mark.asyncio
    async def test_screenshot(self):
        """Test taking screenshot."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                mock_screenshot = MagicMock()
                mock_pyautogui.screenshot.return_value = mock_screenshot

                controller = DesktopController()
                result = await controller.execute({
                    "action": "screenshot",
                    "output_path": "/tmp/test.png"
                })

                mock_screenshot.save.assert_called_once()
                assert result.success is True
                assert "Screenshots saved" in result.output

    @pytest.mark.asyncio
    async def test_get_screen_size(self):
        """Test getting screen size."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.pyautogui") as mock_pyautogui:
                mock_pyautogui.size.return_value = (1920, 1080)

                controller = DesktopController()
                result = await controller.execute({"action": "get_screen_size"})

                assert result.success is True
                assert "1920" in result.output and "1080" in result.output
                assert result.metadata.get("metadata", {}).get("width") == 1920
                assert result.metadata.get("metadata", {}).get("height") == 1080

    @pytest.mark.asyncio
    async def test_get_active_window(self):
        """Test getting active window."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.gw") as mock_gw, \
                 patch("deskflow.tools.desktop.controller.pyautogui"):
                mock_window = MagicMock()
                mock_window.title = "Test Window"
                mock_window.left = 100
                mock_window.top = 50
                mock_window.width = 800
                mock_window.height = 600
                mock_gw.getActiveWindow.return_value = mock_window

                controller = DesktopController()
                result = await controller.execute({"action": "get_active_window"})

                assert result.success is True
                assert "Test Window" in result.output

    @pytest.mark.asyncio
    async def test_window_activate(self):
        """Test activating window."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.gw") as mock_gw, \
                 patch("deskflow.tools.desktop.controller.pyautogui"):
                mock_window = MagicMock()
                mock_gw.getWindowsWithTitle.return_value = [mock_window]

                controller = DesktopController()
                result = await controller.execute({"action": "window_activate", "window_title": "Test"})

                mock_window.activate.assert_called_once()
                assert result.success is True

    @pytest.mark.asyncio
    async def test_window_not_found(self):
        """Test window not found."""
        with patch("deskflow.tools.desktop.controller.PYAUTOGUI_AVAILABLE", True):
            with patch("deskflow.tools.desktop.controller.gw") as mock_gw, \
                 patch("deskflow.tools.desktop.controller.pyautogui"):
                mock_gw.getWindowsWithTitle.return_value = []

                controller = DesktopController()
                result = await controller.execute({"action": "window_activate", "window_title": "NonExistent"})

                assert result.success is False
                assert "not found" in result.error


class TestMouseController:
    """Test MouseController class."""

    def test_mouse_move(self):
        """Test mouse move."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            mouse = MouseController()
            mouse.move(100, 200, duration=1.0)

            mock_execute.assert_called_once_with({
                "action": "mouse_move",
                "x": 100,
                "y": 200,
                "duration": 1.0
            })

    def test_mouse_click(self):
        """Test mouse click."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            mouse = MouseController()
            mouse.click(100, 200, button="right")

            mock_execute.assert_called_once_with({
                "action": "mouse_click",
                "x": 100,
                "y": 200,
                "button": "right"
            })

    def test_mouse_scroll(self):
        """Test mouse scroll."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            mouse = MouseController()
            mouse.scroll(10, x=100, y=200)

            mock_execute.assert_called_once_with({
                "action": "mouse_scroll",
                "amount": 10,
                "x": 100,
                "y": 200
            })

    def test_get_position(self):
        """Test getting mouse position."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            mouse = MouseController()
            mouse.get_position()

            mock_execute.assert_called_once_with({"action": "get_mouse_pos"})


class TestKeyboardController:
    """Test KeyboardController class."""

    def test_press_key(self):
        """Test pressing key."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            keyboard = KeyboardController()
            keyboard.press("enter")

            mock_execute.assert_called_once_with({
                "action": "key_press",
                "key": "enter"
            })

    def test_hotkey(self):
        """Test hotkey combination."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            keyboard = KeyboardController()
            keyboard.hotkey("ctrl", "shift", "esc")

            mock_execute.assert_called_once_with({
                "action": "key_combination",
                "keys": "ctrl+shift+esc"
            })

    def test_write(self):
        """Test typing text."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            keyboard = KeyboardController()
            keyboard.write("Hello", interval=0.1)

            mock_execute.assert_called_once_with({
                "action": "type_text",
                "text": "Hello",
                "interval": 0.1
            })


class TestScreenController:
    """Test ScreenController class."""

    def test_screenshot(self):
        """Test taking screenshot."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            screen = ScreenController()
            screen.screenshot("/tmp/test.png", region=(0, 0, 100, 100))

            mock_execute.assert_called_once_with({
                "action": "screenshot",
                "output_path": "/tmp/test.png",
                "region": [0, 0, 100, 100]
            })

    def test_get_size(self):
        """Test getting screen size."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            screen = ScreenController()
            screen.get_size()

            mock_execute.assert_called_once_with({"action": "get_screen_size"})

    def test_get_active_window(self):
        """Test getting active window."""
        with patch.object(DesktopController, 'execute') as mock_execute:
            screen = ScreenController()
            screen.get_active_window()

            mock_execute.assert_called_once_with({"action": "get_active_window"})
