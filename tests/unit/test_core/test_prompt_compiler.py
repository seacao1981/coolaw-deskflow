"""Tests for prompt compiler module."""

import pytest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

from deskflow.core.prompt_compiler import (
    CompiledPrompt,
    PromptCompiler,
    compile_all,
    check_compiled_outdated,
    load_compiled_identity,
    get_compiler,
)


class TestCompiledPrompt:
    """测试编译后的 Prompt"""

    def test_create_compiled_prompt(self):
        """测试创建编译 Prompt"""
        compiled = CompiledPrompt(
            name="test",
            content="Test content",
            version="2.0",
            token_count=100,
        )
        assert compiled.name == "test"
        assert compiled.token_count == 100

    def test_hash_generation(self):
        """测试哈希生成"""
        compiled1 = CompiledPrompt(name="test", content="Same content")
        compiled2 = CompiledPrompt(name="test", content="Same content")
        assert compiled1.hash == compiled2.hash

    def test_different_content_hash(self):
        """测试不同内容哈希不同"""
        compiled1 = CompiledPrompt(name="test", content="Content A")
        compiled2 = CompiledPrompt(name="test", content="Content B")
        assert compiled1.hash != compiled2.hash

    def test_to_dict(self):
        """测试序列化为字典"""
        compiled = CompiledPrompt(
            name="test",
            content="Test",
            version="2.0",
            token_count=50,
        )
        data = compiled.to_dict()
        assert data["name"] == "test"
        assert data["content"] == "Test"
        assert data["version"] == "2.0"

    def test_from_dict(self):
        """测试从字典反序列化"""
        data = {
            "name": "test",
            "content": "Test content",
            "version": "2.0",
            "token_count": 100,
            "created_at": time.time(),
            "hash": "abc123",
        }
        compiled = CompiledPrompt.from_dict(data)
        assert compiled.name == "test"
        assert compiled.content == "Test content"

    def test_is_expired(self):
        """测试过期检查"""
        compiled = CompiledPrompt(name="test", content="Test")
        assert compiled.is_expired() is False
        compiled.created_at = time.time() - 100000
        assert compiled.is_expired(expiry_seconds=100) is True


class TestPromptCompiler:
    """测试 Prompt 编译器"""

    @pytest.fixture
    def temp_identity_dir(self):
        """创建临时身份目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            soul_file = Path(tmpdir) / "SOUL.md"
            soul_file.write_text("# SOUL\n\nYou are a helpful AI assistant.")
            agent_file = Path(tmpdir) / "AGENT.md"
            agent_file.write_text("# AGENT\n\nYou follow the Ralph Loop.")
            user_file = Path(tmpdir) / "USER.md"
            user_file.write_text("# USER\n\nUser prefers concise responses.")
            yield Path(tmpdir)

    def test_ensure_output_dir(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiler.ensure_output_dir()
        assert compiler.output_dir.exists()

    def test_compile_identity(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiled = compiler.compile_identity()
        assert compiled.name == "identity"
        assert compiled.token_count > 0
        assert "SOUL" in compiled.content

    def test_compile_identity_missing_files(self, temp_identity_dir):
        (temp_identity_dir / "SOUL.md").unlink()
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiled = compiler.compile_identity()
        assert compiled.name == "identity"

    def test_compile_skills(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        mock_catalog = MagicMock()
        mock_catalog.generate_catalog.return_value = "# Skills\n\n- skill1\n- skill2"
        compiled = compiler.compile_skills(mock_catalog)
        assert compiled.name == "skills"
        assert "skill1" in compiled.content

    def test_compile_skills_error_handling(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        mock_catalog = MagicMock()
        mock_catalog.generate_catalog.side_effect = Exception("Test error")
        compiled = compiler.compile_skills(mock_catalog)
        assert compiled.content == ""
        assert compiled.token_count == 0

    def test_compile_mcp(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        mock_catalog = MagicMock()
        mock_catalog.generate_catalog.return_value = "# MCP Servers\n\n- server1"
        compiled = compiler.compile_mcp(mock_catalog)
        assert compiled.name == "mcp"
        assert "server1" in compiled.content

    def test_compile_all(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        mock_catalog = MagicMock()
        mock_catalog.generate_catalog.return_value = "# Skills"
        results = compiler.compile_all(skill_catalog=mock_catalog)
        assert "identity" in results
        assert "skills" in results

    def test_compact_text(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        text = "Line 1\n\n\nLine 2\n\n\n\nLine 3"
        compacted = compiler._compact_text(text)
        assert "\n\n\n" not in compacted

    def test_estimate_tokens(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        text = "Hello World"
        tokens = compiler._estimate_tokens(text)
        assert tokens == len(text) // 4

    def test_save_and_load_compiled(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiled = compiler.compile_identity()
        loaded = compiler.get_compiled("identity")
        assert loaded is not None
        assert loaded.hash == compiled.hash

    def test_cache_save_load(self, temp_identity_dir):
        """测试缓存保存/加载"""
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiler.compile_identity()
        compiler._save_cache()

        compiler2 = PromptCompiler(identity_dir=temp_identity_dir)
        cache = compiler2.load_cache()
        assert "identity" in cache

    def test_is_outdated(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiler.compile_identity()
        assert compiler.is_outdated("identity") is False
        time.sleep(0.1)
        soul_file = temp_identity_dir / "SOUL.md"
        soul_file.write_text("# SOUL\n\nUpdated content")
        assert compiler.is_outdated("identity") is True

    def test_get_compiled_from_file(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        compiler.compile_identity()
        compiler._cache = {}
        loaded = compiler.get_compiled("identity")
        assert loaded is not None


class TestConvenienceFunctions:
    """测试便捷函数"""

    @pytest.fixture
    def temp_identity_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "SOUL.md").write_text("# SOUL")
            yield Path(tmpdir)

    def test_compile_all(self, temp_identity_dir):
        results = compile_all(temp_identity_dir)
        assert "identity" in results

    def test_check_compiled_outdated(self, temp_identity_dir):
        assert check_compiled_outdated(temp_identity_dir) is True
        compile_all(temp_identity_dir)
        assert check_compiled_outdated(temp_identity_dir) is False

    def test_load_compiled_identity(self, temp_identity_dir):
        content = load_compiled_identity(temp_identity_dir)
        assert "# SOUL" in content


class TestPromptCompilerIntegration:
    """集成测试"""

    @pytest.fixture
    def temp_identity_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "SOUL.md").write_text("# SOUL\n\nYou are DeskFlow, an AI assistant.")
            (Path(tmpdir) / "AGENT.md").write_text("# AGENT\n\nYou follow the Ralph Loop methodology.")
            (Path(tmpdir) / "USER.md").write_text("# USER\n\nThe user prefers Python code examples.")
            yield Path(tmpdir)

    def test_full_compilation_cycle(self, temp_identity_dir):
        compiler = PromptCompiler(identity_dir=temp_identity_dir)
        results = compiler.compile_all()
        assert "identity" in results
        assert results["identity"].token_count > 0
        output_file = compiler.output_dir / "identity.compiled.md"
        assert output_file.exists()
        content = output_file.read_text()
        assert "<!-- Compiled Prompt" in content
