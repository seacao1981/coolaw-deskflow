"""Sticker/Emoji tool - Search and manage sticker images.

Provides functionality to:
- Search stickers by keywords
- Get random sticker recommendations
- Manage sticker collections
- Browse stickers by category
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger
from deskflow.tools.base import BaseTool

logger = get_logger(__name__)

# Default sticker storage directory
DEFAULT_STICKER_DIR = Path.home() / ".deskflow" / "stickers"


class StickerTool(BaseTool):
    """Search and manage sticker/emoji images.

    Supports:
    - Search stickers by keywords
    - Get random sticker recommendations
    - List available categories
    - Add stickers to collections
    """

    def __init__(self, sticker_dir: Path | None = None):
        """Initialize sticker tool.

        Args:
            sticker_dir: Directory to store stickers. Defaults to ~/.deskflow/stickers
        """
        self.sticker_dir = sticker_dir or DEFAULT_STICKER_DIR
        self._ensure_sticker_dir()
        self._sticker_index = self._load_sticker_index()

    def _ensure_sticker_dir(self) -> None:
        """Ensure sticker directory exists."""
        self.sticker_dir.mkdir(parents=True, exist_ok=True)
        # Create default categories
        (self.sticker_dir / "favorites").mkdir(exist_ok=True)
        (self.sticker_dir / "downloaded").mkdir(exist_ok=True)

    def _load_sticker_index(self) -> dict[str, list[str]]:
        """Load sticker index from file.

        Returns:
            Dictionary mapping category to list of sticker paths
        """
        index_file = self.sticker_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load sticker index: {e}")
                return self._create_default_index()
        return self._create_default_index()

    def _create_default_index(self) -> dict[str, list[str]]:
        """Create default sticker index.

        Returns:
            Default index structure
        """
        return {
            "favorites": [],
            "downloaded": [],
            "animals": [],
            "emotions": [],
            "actions": [],
            "objects": [],
        }

    def _save_sticker_index(self) -> None:
        """Save sticker index to file."""
        index_file = self.sticker_dir / "index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(self._sticker_index, f, ensure_ascii=False, indent=2)

    def _get_all_stickers(self) -> list[Path]:
        """Get all sticker files in the directory.

        Returns:
            List of Path objects for all sticker files
        """
        extensions = ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]
        stickers = []
        for ext in extensions:
            stickers.extend(self.sticker_dir.rglob(ext))
        return stickers

    def _search_by_filename(self, query: str, stickers: list[Path]) -> list[Path]:
        """Search stickers by filename matching.

        Args:
            query: Search query string
            stickers: List of stickers to search

        Returns:
            List of matching sticker paths
        """
        query_lower = query.lower()
        matches = []
        for sticker in stickers:
            if query_lower in sticker.name.lower():
                matches.append(sticker)
        return matches

    def _get_sticker_metadata(self, sticker_path: Path) -> dict[str, Any]:
        """Get metadata for a sticker file.

        Args:
            sticker_path: Path to sticker file

        Returns:
            Dictionary with sticker metadata
        """
        stat = sticker_path.stat()
        return {
            "filename": sticker_path.name,
            "size_bytes": stat.st_size,
            "category": sticker_path.parent.name,
            "path": str(sticker_path),
        }

    @property
    def name(self) -> str:
        return "sticker"

    @property
    def description(self) -> str:
        return (
            "Search and manage sticker/emoji images. "
            "Can search by keywords, get random recommendations, "
            "browse categories, and manage collections."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": [
                    "search",
                    "random",
                    "list_categories",
                    "list_stickers",
                    "add_to_favorites",
                    "remove_from_favorites",
                ],
            },
            "query": {
                "type": "string",
                "description": "Search query (for search action)",
            },
            "category": {
                "type": "string",
                "description": "Category name (for list_stickers action)",
            },
            "sticker_path": {
                "type": "string",
                "description": "Sticker file path (for add/remove favorites)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 10)",
                "default": 10,
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["action"]

    async def execute(
        self,
        action: str = "",
        query: str | None = None,
        category: str | None = None,
        sticker_path: str | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> Any:
        """Execute sticker tool action.

        Args:
            action: Action to perform
            query: Search query
            category: Category name
            sticker_path: Sticker file path
            limit: Maximum results to return

        Returns:
            ToolResult with action result
        """
        try:
            if action == "search":
                return self._search(query, limit)
            elif action == "random":
                return self._random(limit)
            elif action == "list_categories":
                return self._list_categories()
            elif action == "list_stickers":
                return self._list_stickers(category, limit)
            elif action == "add_to_favorites":
                return self._add_to_favorites(sticker_path)
            elif action == "remove_from_favorites":
                return self._remove_from_favorites(sticker_path)
            else:
                return self._error(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Sticker tool error: {e}")
            return self._error(str(e))

    def _search(self, query: str | None, limit: int) -> Any:
        """Search stickers by keyword.

        Args:
            query: Search keyword
            limit: Maximum results

        Returns:
            ToolResult with search results
        """
        if not query:
            return self._error("Search query is required")

        all_stickers = self._get_all_stickers()
        matches = self._search_by_filename(query, all_stickers)

        if not matches:
            return self._error(f"No stickers found matching: {query}")

        # Limit results
        results = matches[:limit]
        metadata = [self._get_sticker_metadata(p) for p in results]

        return self._success(
            f"Found {len(matches)} stickers matching '{query}', showing {len(results)} results",
            count=len(results),
            total=len(matches),
            stickers=metadata,
        )

    def _random(self, limit: int) -> Any:
        """Get random sticker recommendations.

        Args:
            limit: Number of stickers to return

        Returns:
            ToolResult with random stickers
        """
        all_stickers = self._get_all_stickers()

        if not all_stickers:
            return self._error("No stickers available. Download some stickers first.")

        # Random sample
        count = min(limit, len(all_stickers))
        selected = random.sample(all_stickers, count)
        metadata = [self._get_sticker_metadata(p) for p in selected]

        return self._success(
            f"Randomly selected {count} stickers",
            count=count,
            stickers=metadata,
        )

    def _list_categories(self) -> Any:
        """List available sticker categories.

        Returns:
            ToolResult with category list
        """
        # Find category directories
        categories = set()
        for item in self.sticker_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                categories.add(item.name)

        # Also include index categories
        categories.update(self._sticker_index.keys())

        category_list = sorted(categories)
        counts = {}
        for cat in category_list:
            cat_dir = self.sticker_dir / cat
            if cat_dir.exists():
                count = len(list(cat_dir.glob("*.png")) +
                           list(cat_dir.glob("*.jpg")) +
                           list(cat_dir.glob("*.gif")) +
                           list(cat_dir.glob("*.webp")))
                counts[cat] = count
            else:
                counts[cat] = len(self._sticker_index.get(cat, []))

        return self._success(
            f"Found {len(category_list)} categories",
            categories=category_list,
            counts=counts,
        )

    def _list_stickers(self, category: str | None, limit: int) -> Any:
        """List stickers in a category.

        Args:
            category: Category name
            limit: Maximum results

        Returns:
            ToolResult with sticker list
        """
        if not category:
            # List all stickers
            all_stickers = self._get_all_stickers()
            stickers = all_stickers[:limit]
        else:
            # List stickers in specific category
            cat_dir = self.sticker_dir / category
            if not cat_dir.exists():
                return self._error(f"Category not found: {category}")

            extensions = ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]
            stickers = []
            for ext in extensions:
                stickers.extend(cat_dir.glob(ext))
            stickers = stickers[:limit]

        metadata = [self._get_sticker_metadata(p) for p in stickers]

        return self._success(
            f"Found {len(stickers)} stickers in category '{category or 'all'}'",
            count=len(stickers),
            stickers=metadata,
        )

    def _add_to_favorites(self, sticker_path: str | None) -> Any:
        """Add a sticker to favorites.

        Args:
            sticker_path: Path to sticker file

        Returns:
            ToolResult with result
        """
        if not sticker_path:
            return self._error("Sticker path is required")

        src_path = Path(sticker_path)
        if not src_path.exists():
            return self._error(f"Sticker not found: {sticker_path}")

        # Copy to favorites
        fav_path = self.sticker_dir / "favorites" / src_path.name
        shutil.copy2(src_path, fav_path)

        # Update index
        if str(fav_path) not in self._sticker_index["favorites"]:
            self._sticker_index["favorites"].append(str(fav_path))
            self._save_sticker_index()

        return self._success(f"Added to favorites: {src_path.name}")

    def _remove_from_favorites(self, sticker_path: str | None) -> Any:
        """Remove a sticker from favorites.

        Args:
            sticker_path: Path to sticker file or filename

        Returns:
            ToolResult with result
        """
        if not sticker_path:
            return self._error("Sticker path is required")

        # Check if it's a full path or just filename
        src_path = Path(sticker_path)
        if not src_path.is_absolute():
            src_path = self.sticker_dir / "favorites" / sticker_path

        if not src_path.exists():
            return self._error(f"Sticker not found in favorites: {sticker_path}")

        # Remove file
        src_path.unlink()

        # Update index
        if str(src_path) in self._sticker_index["favorites"]:
            self._sticker_index["favorites"].remove(str(src_path))
            self._save_sticker_index()

        return self._success(f"Removed from favorites: {src_path.name}")
