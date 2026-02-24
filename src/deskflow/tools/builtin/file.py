"""File tool - read, write, and manage files safely."""

from __future__ import annotations

import glob as glob_module
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deskflow.errors import ToolSecurityError
from deskflow.observability.logging import get_logger
from deskflow.tools.base import BaseTool

if TYPE_CHECKING:
    from deskflow.core.models import ToolResult

logger = get_logger(__name__)

MAX_READ_SIZE = 100_000  # 100KB
MAX_WRITE_SIZE = 500_000  # 500KB


class FileTool(BaseTool):
    """Read, write, and manage files with path security.

    Security features:
    - Configurable allowed paths
    - File size limits
    - Path traversal prevention
    """

    def __init__(self, allowed_paths: list[Path] | None = None) -> None:
        self._allowed_paths = allowed_paths or [Path.home()]

    @property
    def name(self) -> str:
        return "file"

    @property
    def description(self) -> str:
        return (
            "Read, write, list, and search files on the filesystem. "
            "Supports operations: read, write, list, search, exists, info."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "operation": {
                "type": "string",
                "description": "Operation: read, write, list, search, exists, info",
                "enum": ["read", "write", "list", "search", "exists", "info"],
            },
            "path": {
                "type": "string",
                "description": "File or directory path",
            },
            "content": {
                "type": "string",
                "description": "Content to write (for write operation)",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern (for search operation)",
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["operation", "path"]

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve a file path.

        Raises:
            ToolSecurityError: If path is outside allowed directories.
        """
        resolved = Path(os.path.expanduser(path)).resolve()

        # Check if path is under an allowed directory
        for allowed in self._allowed_paths:
            allowed_resolved = allowed.resolve()
            try:
                resolved.relative_to(allowed_resolved)
                return resolved
            except ValueError:
                continue

        raise ToolSecurityError(
            "file",
            f"Path '{path}' is outside allowed directories: "
            f"{[str(p) for p in self._allowed_paths]}",
        )

    async def execute(
        self,
        operation: str = "",
        path: str = "",
        content: str | None = None,
        pattern: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a file operation."""
        if not operation or not path:
            return self._error("Both 'operation' and 'path' are required")

        try:
            validated_path = self._validate_path(path)
        except ToolSecurityError as e:
            return self._error(str(e))

        if operation == "read":
            return await self._read(validated_path)
        elif operation == "write":
            return await self._write(validated_path, content or "")
        elif operation == "list":
            return await self._list(validated_path)
        elif operation == "search":
            return await self._search(validated_path, pattern or "*")
        elif operation == "exists":
            exists = validated_path.exists()
            return self._success(f"{'exists' if exists else 'not found'}: {path}")
        elif operation == "info":
            return await self._info(validated_path)
        else:
            return self._error(f"Unknown operation: {operation}")

    async def _read(self, path: Path) -> ToolResult:
        """Read a file."""
        if not path.exists():
            return self._error(f"File not found: {path}")
        if not path.is_file():
            return self._error(f"Not a file: {path}")
        if path.stat().st_size > MAX_READ_SIZE:
            return self._error(
                f"File too large ({path.stat().st_size} bytes). "
                f"Max: {MAX_READ_SIZE} bytes"
            )

        try:
            content = path.read_text(encoding="utf-8")
            return self._success(content, file_path=str(path), size=len(content))
        except UnicodeDecodeError:
            return self._error(f"Cannot read binary file: {path}")
        except Exception as e:
            return self._error(f"Read failed: {e}")

    async def _write(self, path: Path, content: str) -> ToolResult:
        """Write content to a file."""
        if len(content) > MAX_WRITE_SIZE:
            return self._error(
                f"Content too large ({len(content)} chars). Max: {MAX_WRITE_SIZE}"
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return self._success(
                f"Written {len(content)} chars to {path}",
                file_path=str(path),
            )
        except Exception as e:
            return self._error(f"Write failed: {e}")

    async def _list(self, path: Path) -> ToolResult:
        """List directory contents."""
        if not path.exists():
            return self._error(f"Directory not found: {path}")
        if not path.is_dir():
            return self._error(f"Not a directory: {path}")

        try:
            entries: list[str] = []
            for item in sorted(path.iterdir()):
                prefix = "d " if item.is_dir() else "f "
                size = item.stat().st_size if item.is_file() else 0
                entries.append(f"{prefix}{item.name:40s} {size:>10d}")

            output = f"Directory: {path}\n"
            output += f"Total: {len(entries)} items\n\n"
            output += "\n".join(entries[:200])

            if len(entries) > 200:
                output += f"\n... and {len(entries) - 200} more"

            return self._success(output)
        except Exception as e:
            return self._error(f"List failed: {e}")

    async def _search(self, path: Path, pattern: str) -> ToolResult:
        """Search for files matching a glob pattern."""
        try:
            search_pattern = str(path / "**" / pattern)
            matches = glob_module.glob(search_pattern, recursive=True)[:100]
            if matches:
                output = f"Found {len(matches)} matches:\n"
                output += "\n".join(matches)
                return self._success(output)
            return self._success(f"No matches found for pattern: {pattern}")
        except Exception as e:
            return self._error(f"Search failed: {e}")

    async def _info(self, path: Path) -> ToolResult:
        """Get file/directory info."""
        if not path.exists():
            return self._error(f"Not found: {path}")

        stat = path.stat()
        info = {
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "permissions": oct(stat.st_mode),
        }

        output = "\n".join(f"{k}: {v}" for k, v in info.items())
        return self._success(output)
