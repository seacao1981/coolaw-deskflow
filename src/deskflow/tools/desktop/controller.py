"""Desktop control implementation using pyautogui."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from deskflow.tools.base import BaseTool
from deskflow.core.models import ToolResult

try:
    import pyautogui
    import pygetwindow as gw
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None
    gw = None

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScreenInfo:
    """Screen information."""
    width: int
    height: int
    color_depth: int = 24


@dataclass
class WindowInfo:
    """Window information."""
    title: str
    left: int
    top: int
    width: int
    height: int
    is_active: bool


class DesktopController(BaseTool):
    """Desktop controller for mouse, keyboard, and screen operations."""

    name = "desktop"
    description = "Control mouse, keyboard, and screen operations"

    def __init__(self, safety_mode: bool = True):
        """Initialize desktop controller.

        Args:
            safety_mode: If True, adds delays and safety checks
        """
        self.safety_mode = safety_mode
        if PYAUTOGUI_AVAILABLE and safety_mode:
            pyautogui.PAUSE = 0.5  # Safety delay between actions
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort

        super().__init__()

    def to_definition(self) -> dict:
        """Get tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "mouse_move", "mouse_click", "mouse_double_click",
                            "mouse_drag", "mouse_scroll", "get_mouse_pos",
                            "key_press", "key_combination", "type_text",
                            "screenshot", "get_screen_size", "get_active_window",
                            "window_activate", "window_minimize", "window_maximize",
                            "window_close"
                        ],
                        "description": "Action to perform"
                    },
                    "x": {"type": "integer", "description": "X coordinate for mouse actions"},
                    "y": {"type": "integer", "description": "Y coordinate for mouse actions"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": "Mouse button for click actions"
                    },
                    "keys": {
                        "type": "string",
                        "description": "Key or key combination (e.g., 'ctrl+c', 'enter')"
                    },
                    "text": {"type": "string", "description": "Text to type"},
                    "duration": {
                        "type": "number",
                        "description": "Duration in seconds for mouse movement"
                    },
                    "clicks": {
                        "type": "integer",
                        "description": "Number of clicks for double/triple click"
                    },
                    "window_title": {
                        "type": "string",
                        "description": "Window title for window operations"
                    }
                },
                "required": ["action"]
            }
        }

    async def execute(self, params: dict) -> ToolResult:
        """Execute desktop control action.

        Args:
            params: Action parameters

        Returns:
            ToolResult with execution result
        """
        if not PYAUTOGUI_AVAILABLE:
            return self._error("pyautogui and pygetwindow are required. Install with: pip install pyautogui pygetwindow")

        action = params.get("action")

        try:
            if action == "mouse_move":
                return self._mouse_move(params)
            elif action == "mouse_click":
                return self._mouse_click(params)
            elif action == "mouse_double_click":
                return self._mouse_double_click(params)
            elif action == "mouse_drag":
                return self._mouse_drag(params)
            elif action == "mouse_scroll":
                return self._mouse_scroll(params)
            elif action == "get_mouse_pos":
                return self._get_mouse_pos()
            elif action == "key_press":
                return self._key_press(params)
            elif action == "key_combination":
                return self._key_combination(params)
            elif action == "type_text":
                return self._type_text(params)
            elif action == "screenshot":
                return self._screenshot(params)
            elif action == "get_screen_size":
                return self._get_screen_size()
            elif action == "get_active_window":
                return self._get_active_window()
            elif action == "window_activate":
                return self._window_activate(params)
            elif action == "window_minimize":
                return self._window_minimize(params)
            elif action == "window_maximize":
                return self._window_maximize(params)
            elif action == "window_close":
                return self._window_close(params)
            else:
                return self._error(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Desktop control error: {e}")
            return self._error(str(e))

    def _mouse_move(self, params: dict) -> ToolResult:
        """Move mouse to position."""
        x = params.get("x", 0)
        y = params.get("y", 0)
        duration = params.get("duration", 0.5)

        pyautogui.moveTo(x, y, duration=duration)
        return self._success(f"Mouse moved to ({x}, {y})")

    def _mouse_click(self, params: dict) -> ToolResult:
        """Click mouse at position."""
        x = params.get("x")
        y = params.get("y")
        button = params.get("button", "left")

        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
            return self._success(f"Clicked at ({x}, {y}) with {button} button")
        else:
            pyautogui.click(button=button)
            return self._success(f"Clicked at current position with {button} button")

    def _mouse_double_click(self, params: dict) -> ToolResult:
        """Double click mouse at position."""
        x = params.get("x")
        y = params.get("y")

        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
            return self._success(f"Double clicked at ({x}, {y})")
        else:
            pyautogui.doubleClick()
            return self._success("Double clicked at current position")

    def _mouse_drag(self, params: dict) -> ToolResult:
        """Drag mouse from one position to another."""
        start_x = params.get("start_x", 0)
        start_y = params.get("start_y", 0)
        end_x = params.get("end_x", 0)
        end_y = params.get("end_y", 0)
        duration = params.get("duration", 0.5)

        pyautogui.drag(start_x, start_y, end_x, end_y, duration=duration)
        return self._success(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")

    def _mouse_scroll(self, params: dict) -> ToolResult:
        """Scroll mouse wheel."""
        amount = params.get("amount", 1)
        x = params.get("x")
        y = params.get("y")

        if x is not None and y is not None:
            pyautogui.scroll(amount, x=x, y=y)
            return self._success(f"Scrolled {amount} at ({x}, {y})")
        else:
            pyautogui.scroll(amount)
            return self._success(f"Scrolled {amount}")

    def _get_mouse_pos(self) -> ToolResult:
        """Get current mouse position."""
        x, y = pyautogui.position()
        return self._success(f"Mouse position: ({x}, {y})", metadata={"x": x, "y": y})

    def _key_press(self, params: dict) -> ToolResult:
        """Press a key."""
        key = params.get("key", params.get("keys", ""))

        pyautogui.press(key)
        return self._success(f"Pressed key: {key}")

    def _key_combination(self, params: dict) -> ToolResult:
        """Press key combination."""
        keys = params.get("keys", params.get("key", ""))
        key_list = keys.split("+")

        pyautogui.hotkey(*key_list)
        return self._success(f"Pressed key combination: {keys}")

    def _type_text(self, params: dict) -> ToolResult:
        """Type text."""
        text = params.get("text", "")
        interval = params.get("interval", 0.05)

        pyautogui.write(text, interval=interval)
        return self._success(f"Typed: {text}")

    def _screenshot(self, params: dict) -> ToolResult:
        """Take a screenshot."""
        region = params.get("region")  # (left, top, width, height)
        output_path = params.get("output_path")

        screenshot = pyautogui.screenshot(region=tuple(region) if region else None)

        if not output_path:
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )

        screenshot.save(output_path)
        return self._success(f"Screenshots saved to: {output_path}", metadata={"path": output_path})

    def _get_screen_size(self) -> ToolResult:
        """Get screen size."""
        width, height = pyautogui.size()
        return self._success(
            f"Screen size: {width}x{height}",
            metadata={"width": width, "height": height}
        )

    def _get_active_window(self) -> ToolResult:
        """Get active window info."""
        if gw is None:
            return self._error("pygetwindow not available")

        active = gw.getActiveWindow()
        if active:
            return self._success(
                f"Active window: {active.title}",
                metadata={
                    "title": active.title,
                    "left": active.left,
                    "top": active.top,
                    "width": active.width,
                    "height": active.height
                }
            )
        return self._success("No active window found")

    def _window_activate(self, params: dict) -> ToolResult:
        """Activate a window by title."""
        if gw is None:
            return self._error("pygetwindow not available")

        title = params.get("window_title", "")
        windows = gw.getWindowsWithTitle(title)

        if windows:
            windows[0].activate()
            return self._success(f"Activated window: {title}")
        return self._error(f"Window not found: {title}")

    def _window_minimize(self, params: dict) -> ToolResult:
        """Minimize a window."""
        if gw is None:
            return self._error("pygetwindow not available")

        title = params.get("window_title", "")
        windows = gw.getWindowsWithTitle(title)

        if windows:
            windows[0].minimize()
            return self._success(f"Minimized window: {title}")
        return self._error(f"Window not found: {title}")

    def _window_maximize(self, params: dict) -> ToolResult:
        """Maximize a window."""
        if gw is None:
            return self._error("pygetwindow not available")

        title = params.get("window_title", "")
        windows = gw.getWindowsWithTitle(title)

        if windows:
            windows[0].maximize()
            return self._success(f"Maximized window: {title}")
        return self._error(f"Window not found: {title}")

    def _window_close(self, params: dict) -> ToolResult:
        """Close a window."""
        if gw is None:
            return self._error("pygetwindow not available")

        title = params.get("window_title", "")
        windows = gw.getWindowsWithTitle(title)

        if windows:
            windows[0].close()
            return self._success(f"Closed window: {title}")
        return self._error(f"Window not found: {title}")


class MouseController:
    """Dedicated mouse controller."""

    def __init__(self, safety_mode: bool = True):
        self.desktop = DesktopController(safety_mode=safety_mode)

    def move(self, x: int, y: int, duration: float = 0.5) -> ToolResult:
        """Move mouse to position."""
        return self.desktop.execute({"action": "mouse_move", "x": x, "y": y, "duration": duration})

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> ToolResult:
        """Click mouse."""
        params = {"action": "mouse_click", "button": button}
        if x is not None and y is not None:
            params["x"] = x
            params["y"] = y
        return self.desktop.execute(params)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> ToolResult:
        """Double click mouse."""
        params = {"action": "mouse_double_click"}
        if x is not None and y is not None:
            params["x"] = x
            params["y"] = y
        return self.desktop.execute(params)

    def scroll(self, amount: int, x: Optional[int] = None, y: Optional[int] = None) -> ToolResult:
        """Scroll mouse wheel."""
        params = {"action": "mouse_scroll", "amount": amount}
        if x is not None and y is not None:
            params["x"] = x
            params["y"] = y
        return self.desktop.execute(params)

    def get_position(self) -> ToolResult:
        """Get current mouse position."""
        return self.desktop.execute({"action": "get_mouse_pos"})


class KeyboardController:
    """Dedicated keyboard controller."""

    def __init__(self, safety_mode: bool = True):
        self.desktop = DesktopController(safety_mode=safety_mode)

    def press(self, key: str) -> ToolResult:
        """Press a key."""
        return self.desktop.execute({"action": "key_press", "key": key})

    def hotkey(self, *keys: str) -> ToolResult:
        """Press key combination."""
        return self.desktop.execute({"action": "key_combination", "keys": "+".join(keys)})

    def write(self, text: str, interval: float = 0.05) -> ToolResult:
        """Type text."""
        return self.desktop.execute({"action": "type_text", "text": text, "interval": interval})


class ScreenController:
    """Dedicated screen controller."""

    def __init__(self):
        self.desktop = DesktopController()

    def screenshot(self, output_path: Optional[str] = None, region: Optional[tuple] = None) -> ToolResult:
        """Take a screenshot."""
        params = {"action": "screenshot"}
        if output_path:
            params["output_path"] = output_path
        if region:
            params["region"] = list(region)
        return self.desktop.execute(params)

    def get_size(self) -> ToolResult:
        """Get screen size."""
        return self.desktop.execute({"action": "get_screen_size"})

    def get_active_window(self) -> ToolResult:
        """Get active window info."""
        return self.desktop.execute({"action": "get_active_window"})
