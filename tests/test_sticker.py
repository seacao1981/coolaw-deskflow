"""Tests for sticker tool."""

import shutil
import tempfile
from pathlib import Path

import pytest

from deskflow.tools.builtin.sticker import StickerTool


class TestStickerTool:
    """Test StickerTool class."""

    @pytest.fixture
    def temp_sticker_dir(self):
        """Create temporary sticker directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sticker_tool(self, temp_sticker_dir):
        """Create StickerTool with temporary directory."""
        return StickerTool(sticker_dir=temp_sticker_dir)

    def test_init_default(self, temp_sticker_dir):
        """Test default initialization."""
        # Use a subdirectory to avoid modifying home directory
        test_dir = temp_sticker_dir / "test_stickers"
        tool = StickerTool(sticker_dir=test_dir)

        assert tool.sticker_dir == test_dir
        assert test_dir.exists()
        assert (test_dir / "favorites").exists()
        assert (test_dir / "downloaded").exists()

    def test_name_property(self, sticker_tool):
        """Test name property."""
        assert sticker_tool.name == "sticker"

    def test_description_property(self, sticker_tool):
        """Test description property."""
        description = sticker_tool.description
        assert "sticker" in description.lower()
        assert "search" in description.lower()

    def test_parameters_property(self, sticker_tool):
        """Test parameters property."""
        params = sticker_tool.parameters

        assert "action" in params
        assert "query" in params
        assert "category" in params
        assert "limit" in params

        # Check action enum values
        action_enum = params["action"]["enum"]
        assert "search" in action_enum
        assert "random" in action_enum
        assert "list_categories" in action_enum
        assert "list_stickers" in action_enum

    def test_required_params_property(self, sticker_tool):
        """Test required_params property."""
        assert sticker_tool.required_params == ["action"]

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, sticker_tool):
        """Test unknown action handling."""
        result = await sticker_tool.execute(action="unknown_action")

        assert result.success is False
        assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_execute_search_no_query(self, sticker_tool):
        """Test search without query."""
        result = await sticker_tool.execute(action="search")

        assert result.success is False
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_execute_search_not_found(self, sticker_tool):
        """Test search with no results."""
        result = await sticker_tool.execute(action="search", query="nonexistent")

        assert result.success is False
        assert "No stickers found" in result.error

    @pytest.mark.asyncio
    async def test_execute_search_success(self, sticker_tool, temp_sticker_dir):
        """Test successful search."""
        # Create test sticker files
        test_cat = temp_sticker_dir / "test"
        test_cat.mkdir()
        (test_cat / "happy_face.png").touch()
        (test_cat / "sad_face.png").touch()
        (test_cat / "excited_face.png").touch()

        # Reload index
        sticker_tool._load_sticker_index()

        result = await sticker_tool.execute(action="search", query="face")

        assert result.success is True
        assert "Found" in result.output
        assert result.metadata.get("count", 0) > 0

    @pytest.mark.asyncio
    async def test_execute_random_no_stickers(self, sticker_tool):
        """Test random with no stickers."""
        result = await sticker_tool.execute(action="random", limit=5)

        assert result.success is False
        assert "No stickers available" in result.error

    @pytest.mark.asyncio
    async def test_execute_random_success(self, sticker_tool, temp_sticker_dir):
        """Test successful random selection."""
        # Create test sticker files
        test_cat = temp_sticker_dir / "test"
        test_cat.mkdir()
        for i in range(10):
            (test_cat / f"sticker_{i}.png").touch()

        result = await sticker_tool.execute(action="random", limit=5)

        assert result.success is True
        assert "Randomly selected" in result.output
        assert result.metadata.get("count", 0) == 5

    @pytest.mark.asyncio
    async def test_execute_random_limit_exceeded(self, sticker_tool, temp_sticker_dir):
        """Test random with limit exceeding available stickers."""
        # Create only 3 stickers
        test_cat = temp_sticker_dir / "test"
        test_cat.mkdir()
        for i in range(3):
            (test_cat / f"sticker_{i}.png").touch()

        result = await sticker_tool.execute(action="random", limit=10)

        assert result.success is True
        assert result.metadata.get("count", 0) == 3

    @pytest.mark.asyncio
    async def test_execute_list_categories(self, sticker_tool, temp_sticker_dir):
        """Test listing categories."""
        # Create category directories
        (temp_sticker_dir / "animals").mkdir()
        (temp_sticker_dir / "emotions").mkdir()
        # favorites already exists from initialization

        result = await sticker_tool.execute(action="list_categories")

        assert result.success is True
        assert "categories" in result.metadata
        categories = result.metadata.get("categories", [])
        assert "animals" in categories
        assert "emotions" in categories
        assert "favorites" in categories

    @pytest.mark.asyncio
    async def test_execute_list_stickers_all(self, sticker_tool, temp_sticker_dir):
        """Test listing all stickers."""
        # Create test stickers
        test_cat = temp_sticker_dir / "test"
        test_cat.mkdir()
        for i in range(5):
            (test_cat / f"sticker_{i}.png").touch()

        result = await sticker_tool.execute(action="list_stickers")

        assert result.success is True
        assert result.metadata.get("count", 0) > 0

    @pytest.mark.asyncio
    async def test_execute_list_stickers_by_category(self, sticker_tool, temp_sticker_dir):
        """Test listing stickers in specific category."""
        # Create category with stickers
        animals_cat = temp_sticker_dir / "animals"
        animals_cat.mkdir()
        for i in range(3):
            (animals_cat / f"animal_{i}.gif").touch()

        result = await sticker_tool.execute(
            action="list_stickers",
            category="animals"
        )

        assert result.success is True
        assert "animals" in result.output
        assert result.metadata.get("count", 0) == 3

    @pytest.mark.asyncio
    async def test_execute_list_stickers_category_not_found(self, sticker_tool):
        """Test listing stickers in non-existent category."""
        result = await sticker_tool.execute(
            action="list_stickers",
            category="nonexistent"
        )

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_add_to_favorites_no_path(self, sticker_tool):
        """Test add to favorites without path."""
        result = await sticker_tool.execute(action="add_to_favorites")

        assert result.success is False
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_execute_add_to_favorites_not_found(self, sticker_tool):
        """Test add to favorites with non-existent file."""
        result = await sticker_tool.execute(
            action="add_to_favorites",
            sticker_path="/nonexistent/path.png"
        )

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_add_to_favorites_success(self, sticker_tool, temp_sticker_dir):
        """Test successful add to favorites."""
        # Create source sticker
        source_path = temp_sticker_dir / "source" / "test.png"
        source_path.parent.mkdir()
        source_path.touch()

        result = await sticker_tool.execute(
            action="add_to_favorites",
            sticker_path=str(source_path)
        )

        assert result.success is True
        assert "Added to favorites" in result.output

        # Verify file was copied
        fav_path = temp_sticker_dir / "favorites" / "test.png"
        assert fav_path.exists()

    @pytest.mark.asyncio
    async def test_execute_remove_from_favorites_no_path(self, sticker_tool):
        """Test remove from favorites without path."""
        result = await sticker_tool.execute(action="remove_from_favorites")

        assert result.success is False
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_execute_remove_from_favorites_not_found(self, sticker_tool):
        """Test remove from favorites with non-existent file."""
        result = await sticker_tool.execute(
            action="remove_from_favorites",
            sticker_path="nonexistent.png"
        )

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_remove_from_favorites_success(self, sticker_tool, temp_sticker_dir):
        """Test successful remove from favorites."""
        # Create favorite sticker (favorites dir already exists from init)
        fav_path = temp_sticker_dir / "favorites" / "test.png"
        fav_path.touch()

        result = await sticker_tool.execute(
            action="remove_from_favorites",
            sticker_path="test.png"
        )

        assert result.success is True
        assert "Removed from favorites" in result.output

        # Verify file was removed
        assert not fav_path.exists()

    def test_get_all_stickers(self, sticker_tool, temp_sticker_dir):
        """Test getting all stickers."""
        # Create stickers with different extensions
        test_cat = temp_sticker_dir / "test"
        test_cat.mkdir()
        (test_cat / "image1.png").touch()
        (test_cat / "image2.jpg").touch()
        (test_cat / "image3.gif").touch()
        (test_cat / "image4.webp").touch()
        (test_cat / "document.txt").touch()  # Should not be included

        stickers = sticker_tool._get_all_stickers()

        assert len(stickers) == 4

    def test_search_by_filename(self, sticker_tool):
        """Test searching by filename."""
        # Create mock paths
        stickers = [
            Path("/test/happy_cat.png"),
            Path("/test/sad_cat.png"),
            Path("/test/dog.png"),
            Path("/test/cat_toys.gif"),
        ]

        # Search for "cat"
        results = sticker_tool._search_by_filename("cat", stickers)

        assert len(results) == 3
        assert Path("/test/happy_cat.png") in results
        assert Path("/test/sad_cat.png") in results
        assert Path("/test/cat_toys.gif") in results

    def test_search_by_filename_case_insensitive(self, sticker_tool):
        """Test case-insensitive search."""
        stickers = [
            Path("/test/HappyCat.png"),
            Path("/test/SAD_CAT.png"),
            Path("/test/dog.png"),
        ]

        results = sticker_tool._search_by_filename("CAT", stickers)

        assert len(results) == 2

    def test_get_sticker_metadata(self, sticker_tool, temp_sticker_dir):
        """Test getting sticker metadata."""
        # Create test file
        test_path = temp_sticker_dir / "test" / "emoji.png"
        test_path.parent.mkdir()
        test_path.touch()

        metadata = sticker_tool._get_sticker_metadata(test_path)

        assert metadata["filename"] == "emoji.png"
        assert metadata["category"] == "test"
        assert metadata["size_bytes"] == 0
        assert "path" in metadata

    def test_sticker_index_persistence(self, temp_sticker_dir):
        """Test that sticker index is persisted to disk."""
        tool = StickerTool(sticker_dir=temp_sticker_dir)

        # Modify index
        tool._sticker_index["test"] = ["path1.png", "path2.png"]
        tool._save_sticker_index()

        # Create new instance
        tool2 = StickerTool(sticker_dir=temp_sticker_dir)

        # Verify index was loaded
        assert "test" in tool2._sticker_index
        assert tool2._sticker_index["test"] == ["path1.png", "path2.png"]

    def test_sticker_index_corrupt_handling(self, temp_sticker_dir):
        """Test handling of corrupt index file."""
        # Write corrupt JSON
        index_file = temp_sticker_dir / "index.json"
        with open(index_file, "w") as f:
            f.write("{ corrupt json }")

        # Should not raise, should create default index
        tool = StickerTool(sticker_dir=temp_sticker_dir)
        assert "favorites" in tool._sticker_index
        assert "downloaded" in tool._sticker_index
