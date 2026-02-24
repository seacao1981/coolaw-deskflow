"""
技能加载器

遵循 Agent Skills 规范 (agentskills.io/specification)
从标准目录结构加载 SKILL.md 定义的技能
"""

import logging
from pathlib import Path

from .parser import ParsedSkill, SkillParser
from .registry import SkillRegistry

logger = logging.getLogger(__name__)


def _builtin_skills_root() -> Path | None:
    """
    返回内置技能目录（随 wheel 分发）。

    期望结构：
    deskflow/
      builtin_skills/
        system/<tool-name>/SKILL.md
    """
    try:
        root = Path(__file__).resolve().parents[1] / "builtin_skills"
        return root if root.exists() and root.is_dir() else None
    except Exception:
        return None


# 标准技能目录 (按优先级排序)
SKILL_DIRECTORIES = [
    # 内置系统技能（随 pip 包分发，优先级最高）
    "__builtin__",
    # 用户工作区（用户安装/创建的技能）
    "~/.deskflow/skills",
    # 项目级别
    ".claude/skills",
    "skills",
    # 用户级别 (全局)
    "~/.claude/skills",
]


class SkillLoader:
    """
    技能加载器

    支持:
    - 从标准目录自动发现技能
    - 解析 SKILL.md 文件
    - 加载技能脚本
    - 渐进式披露
    """

    def __init__(
        self,
        registry: SkillRegistry | None = None,
        parser: SkillParser | None = None,
    ):
        self.registry = registry if registry is not None else SkillRegistry()
        self.parser = parser or SkillParser()
        self._loaded_skills: dict[str, ParsedSkill] = {}

    def discover_skill_directories(self, base_path: Path | str | None = None) -> list[Path]:
        """
        发现所有技能目录

        Args:
            base_path: 基础路径 (项目根目录)

        Returns:
            存在的技能目录列表
        """
        if isinstance(base_path, str):
            base_path = Path(base_path)
        base_path = base_path or Path.cwd()
        directories = []

        for skill_dir in SKILL_DIRECTORIES:
            if skill_dir == "__builtin__":
                builtin = _builtin_skills_root()
                if builtin is not None:
                    directories.append(builtin)
                    logger.debug(f"Found builtin skill directory: {builtin}")
                continue

            if skill_dir.startswith("~"):
                path = Path(skill_dir).expanduser()
            else:
                path = base_path / skill_dir

            if path.exists() and path.is_dir():
                directories.append(path)
                logger.debug(f"Found skill directory: {path}")

        return directories

    def load_skills_from_directory(self, directory: Path) -> list[ParsedSkill]:
        """
        从目录加载所有技能

        Args:
            directory: 技能目录

        Returns:
            加载的技能列表
        """
        if not directory.exists():
            logger.warning(f"Skill directory does not exist: {directory}")
            return []

        skills = []

        # 查找所有包含 SKILL.md 的子目录
        for item in directory.iterdir():
            if not item.is_dir():
                continue

            # 检查是否是系统技能子目录 (如 system/)
            if item.name == "system":
                system_skills = self.load_skills_from_directory(item)
                skills.extend(system_skills)
                continue

            # 检查是否有 SKILL.md 文件
            skill_md = item / "SKILL.md"
            if skill_md.exists():
                try:
                    parsed = self.parser.parse_file(skill_md)
                    skills.append(parsed)
                    logger.info(f"Loaded skill: {parsed.metadata.name}")
                except Exception as e:
                    logger.warning(f"Failed to parse skill {item.name}: {e}")

        return skills

    def load_all_skills(self, base_path: Path | str | None = None) -> int:
        """
        加载所有技能并注册

        Args:
            base_path: 基础路径

        Returns:
            加载的技能数量
        """
        directories = self.discover_skill_directories(base_path)
        total_loaded = 0

        for directory in directories:
            skills = self.load_skills_from_directory(directory)
            for skill in skills:
                self.registry.register(skill)
                self._loaded_skills[skill.metadata.name] = skill
                total_loaded += 1

        logger.info(f"Loaded {total_loaded} skills from {len(directories)} directories")
        return total_loaded

    def reload_skill(self, name: str) -> bool:
        """
        重新加载技能

        Args:
            name: 技能名称

        Returns:
            是否成功
        """
        if name not in self._loaded_skills:
            return False

        old_skill = self._loaded_skills[name]
        skill_dir = old_skill.path.parent

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return False

        try:
            parsed = self.parser.parse_file(skill_md)
            self.registry.register(parsed)
            self._loaded_skills[name] = parsed
            logger.info(f"Reloaded skill: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to reload skill {name}: {e}")
            return False

    def get_loaded_skills(self) -> dict[str, ParsedSkill]:
        """获取已加载的技能字典"""
        return self._loaded_skills.copy()
