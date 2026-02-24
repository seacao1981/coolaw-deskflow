"""
Prompt 编译器

功能:
- 预编译身份文件（减少运行时 token 消耗）
- 懒加载组件
- 增量更新
- Token 优化
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

# 编译输出目录
COMPILED_DIR_NAME = "compiled"
# 编译缓存文件
COMPILED_CACHE_FILE = ".compiled_cache.json"
# 过期时间（秒）- 默认 24 小时
DEFAULT_EXPIRY_SECONDS = 24 * 60 * 60


class CompiledPrompt:
    """编译后的 Prompt"""

    def __init__(
        self,
        name: str,
        content: str,
        version: str = "1.0",
        token_count: int = 0,
    ) -> None:
        self.name = name
        self.content = content
        self.version = version
        self.token_count = token_count
        self.created_at = time.time()
        self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content": self.content,
            "version": self.version,
            "token_count": self.token_count,
            "created_at": self.created_at,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompiledPrompt":
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
            version=data.get("version", "1.0"),
            token_count=data.get("token_count", 0),
        )

    def is_expired(self, expiry_seconds: int = DEFAULT_EXPIRY_SECONDS) -> bool:
        """检查是否过期"""
        return (time.time() - self.created_at) > expiry_seconds


class PromptCompiler:
    """
    Prompt 编译器

    将身份文件、技能目录等预编译为低 token 版本
    """

    def __init__(
        self,
        identity_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> None:
        if identity_dir:
            self.identity_dir = Path(identity_dir)
        else:
            from deskflow.config import settings
            self.identity_dir = settings.identity_path

        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.identity_dir / COMPILED_DIR_NAME

        self._cache: dict[str, CompiledPrompt] = {}
        self._cache_file = self.output_dir / COMPILED_CACHE_FILE

    def ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compile_identity(self, name: str = "identity") -> CompiledPrompt:
        """
        编译身份文件

        将 SOUL, AGENT, USER 等文件合并为紧凑格式
        """
        self.ensure_output_dir()

        identity_files = ["SOUL.md", "AGENT.md", "USER.md"]
        sections = []

        for filename in identity_files:
            filepath = self.identity_dir / filename
            if filepath.exists():
                content = self._compact_text(filepath.read_text(encoding="utf-8"))
                sections.append(f"### {filename.replace('.md', '').lower()}\n\n{content}")

        compiled_content = "\n\n".join(sections)
        token_count = self._estimate_tokens(compiled_content)

        compiled = CompiledPrompt(
            name=name,
            content=compiled_content,
            version="2.0",
            token_count=token_count,
        )

        # 保存到文件
        self._save_compiled(compiled)
        self._cache[name] = compiled

        logger.info(
            f"[PromptCompiler] Compiled identity: {name}, "
            f"tokens={token_count}, hash={compiled.hash}"
        )

        return compiled

    def compile_skills(self, skill_catalog: Any, name: str = "skills") -> CompiledPrompt:
        """编译技能目录"""
        self.ensure_output_dir()

        try:
            if hasattr(skill_catalog, "generate_catalog"):
                catalog_text = skill_catalog.generate_catalog()
            else:
                catalog_text = str(skill_catalog)

            # 压缩格式
            compact_text = self._compact_text(catalog_text)
            token_count = self._estimate_tokens(compact_text)

            compiled = CompiledPrompt(
                name=name,
                content=compact_text,
                version="2.0",
                token_count=token_count,
            )

            self._save_compiled(compiled)
            self._cache[name] = compiled

            logger.info(
                f"[PromptCompiler] Compiled skills: {name}, "
                f"tokens={token_count}, hash={compiled.hash}"
            )

            return compiled

        except Exception as e:
            logger.warning(f"[PromptCompiler] Failed to compile skills: {e}")
            return CompiledPrompt(
                name=name,
                content="",
                version="2.0",
                token_count=0,
            )

    def compile_mcp(self, mcp_catalog: Any, name: str = "mcp") -> CompiledPrompt:
        """编译 MCP 目录"""
        self.ensure_output_dir()

        try:
            if hasattr(mcp_catalog, "generate_catalog"):
                catalog_text = mcp_catalog.generate_catalog()
            else:
                catalog_text = str(mcp_catalog)

            compact_text = self._compact_text(catalog_text)
            token_count = self._estimate_tokens(compact_text)

            compiled = CompiledPrompt(
                name=name,
                content=compact_text,
                version="2.0",
                token_count=token_count,
            )

            self._save_compiled(compiled)
            self._cache[name] = compiled

            logger.info(
                f"[PromptCompiler] Compiled MCP: {name}, "
                f"tokens={token_count}, hash={compiled.hash}"
            )

            return compiled

        except Exception as e:
            logger.warning(f"[PromptCompiler] Failed to compile MCP: {e}")
            return CompiledPrompt(
                name=name,
                content="",
                version="2.0",
                token_count=0,
            )

    def compile_all(
        self,
        skill_catalog: Any | None = None,
        mcp_catalog: Any | None = None,
    ) -> dict[str, CompiledPrompt]:
        """编译所有组件"""
        results = {}

        results["identity"] = self.compile_identity()

        if skill_catalog:
            results["skills"] = self.compile_skills(skill_catalog)

        if mcp_catalog:
            results["mcp"] = self.compile_mcp(mcp_catalog)

        # 保存缓存
        self._save_cache()

        logger.info(
            f"[PromptCompiler] Compiled all components: "
            f"{len(results)} files, "
            f"total_tokens={sum(c.token_count for c in results.values())}"
        )

        return results

    def _compact_text(self, text: str) -> str:
        """压缩文本（移除多余空行和空格）"""
        lines = text.split("\n")
        compacted = []
        prev_empty = False

        for line in lines:
            stripped = line.rstrip()

            if not stripped:
                if not prev_empty:
                    compacted.append("")
                prev_empty = True
            else:
                compacted.append(stripped)
                prev_empty = False

        return "\n".join(compacted)

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数（~4 字符/token）"""
        return len(text) // 4

    def _save_compiled(self, compiled: CompiledPrompt) -> None:
        """保存编译结果到文件"""
        filepath = self.output_dir / f"{compiled.name}.compiled.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"<!-- Compiled Prompt v{compiled.version} -->\n")
            f.write(f"<!-- Hash: {compiled.hash} -->\n")
            f.write(f"<!-- Tokens: {compiled.token_count} -->\n")
            f.write(f"<!-- Created: {time.strftime('%Y-%m-%d %H:%M:%S')} -->\n\n")
            f.write(compiled.content)

    def _save_cache(self) -> None:
        """保存缓存"""
        try:
            cache_data = {
                name: compiled.to_dict()
                for name, compiled in self._cache.items()
            }
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            logger.warning(f"[PromptCompiler] Failed to save cache: {e}")

    def load_cache(self) -> dict[str, CompiledPrompt]:
        """加载缓存"""
        if not self._cache_file.exists():
            return {}

        try:
            with open(self._cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)

            self._cache = {
                name: CompiledPrompt.from_dict(data)
                for name, data in cache_data.items()
            }

            logger.info(f"[PromptCompiler] Loaded cache: {len(self._cache)} entries")
            return self._cache

        except Exception as e:
            logger.warning(f"[PromptCompiler] Failed to load cache: {e}")
            return {}

    def get_compiled(self, name: str) -> CompiledPrompt | None:
        """获取编译后的 Prompt"""
        if name in self._cache:
            return self._cache[name]

        # 尝试从文件加载
        filepath = self.output_dir / f"{name}.compiled.md"
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            # 移除注释行
            lines = [
                line for line in content.split("\n")
                if not line.startswith("<!--")
            ]
            return CompiledPrompt(
                name=name,
                content="\n".join(lines),
                version="2.0",
            )

        return None

    def is_outdated(self, name: str = "identity") -> bool:
        """检查是否需要重新编译"""
        if name not in self._cache:
            # 尝试加载
            compiled = self.get_compiled(name)
            if compiled is None:
                return True
            self._cache[name] = compiled

        compiled = self._cache[name]

        # 检查是否过期
        if compiled.is_expired():
            return True

        # 检查源文件是否有变化
        source_files = ["SOUL.md", "AGENT.md", "USER.md"]
        for filename in source_files:
            filepath = self.identity_dir / filename
            if filepath.exists():
                mtime = filepath.stat().st_mtime
                if mtime > compiled.created_at:
                    return True

        return False


# ==================== 便捷函数 ====================

def compile_all(
    identity_dir: Path | str,
    skill_catalog: Any | None = None,
    mcp_catalog: Any | None = None,
) -> dict[str, CompiledPrompt]:
    """编译所有组件"""
    compiler = PromptCompiler(identity_dir=identity_dir)
    return compiler.compile_all(skill_catalog, mcp_catalog)


def check_compiled_outdated(identity_dir: Path | str) -> bool:
    """检查是否需要重新编译"""
    compiler = PromptCompiler(identity_dir=identity_dir)
    return compiler.is_outdated("identity")


def load_compiled_identity(identity_dir: Path | str) -> str:
    """加载编译后的身份文件"""
    compiler = PromptCompiler(identity_dir=identity_dir)

    if compiler.is_outdated():
        compiler.compile_identity()

    compiled = compiler.get_compiled("identity")
    return compiled.content if compiled else ""


# ==================== 全局单例 ====================

_compiler: PromptCompiler | None = None


def get_compiler(identity_dir: Path | str | None = None) -> PromptCompiler:
    """获取编译器单例"""
    global _compiler
    if _compiler is None:
        _compiler = PromptCompiler(identity_dir=identity_dir)
    return _compiler
