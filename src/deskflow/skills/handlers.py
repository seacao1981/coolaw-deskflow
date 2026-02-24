"""
技能管理处理器

处理技能管理相关的系统技能：
- list_skills: 列出技能
- get_skill_info: 获取技能信息
- run_skill_script: 运行技能脚本
- get_skill_reference: 获取参考文档
- install_skill: 安装技能
- load_skill: 加载新创建的技能
- reload_skill: 重新加载已修改的技能
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deskflow.core.agent import Agent

logger = logging.getLogger(__name__)

# Skill 内容专用阈值
SKILL_MAX_CHARS = 64000


class SkillsHandler:
    """技能管理处理器"""

    TOOLS = [
        "list_skills",
        "get_skill_info",
        "run_skill_script",
        "get_skill_reference",
        "install_skill",
        "load_skill",
        "reload_skill",
    ]

    def __init__(self, agent: "Agent"):
        self.agent = agent

    async def handle(self, tool_name: str, params: dict[str, Any]) -> str:
        """处理工具调用"""
        if tool_name == "list_skills":
            return self._list_skills(params)
        elif tool_name == "get_skill_info":
            return self._get_skill_info(params)
        elif tool_name == "run_skill_script":
            return self._run_skill_script(params)
        elif tool_name == "get_skill_reference":
            return self._get_skill_reference(params)
        elif tool_name == "install_skill":
            return await self._install_skill(params)
        elif tool_name == "load_skill":
            return self._load_skill(params)
        elif tool_name == "reload_skill":
            return self._reload_skill(params)
        else:
            return f"Unknown skills tool: {tool_name}"

    def _list_skills(self, params: dict) -> str:
        """列出所有技能"""
        if not hasattr(self.agent, 'skill_registry') or self.agent.skill_registry is None:
            return "技能系统未初始化"
        
        skills = self.agent.skill_registry.list_all()
        if not skills:
            return "当前没有已安装的技能\n\n提示：技能应放在 skills/ 目录下，每个技能是一个包含 SKILL.md 的文件夹"

        # 分类显示
        system_skills = [s for s in skills if s.system]
        external_skills = [s for s in skills if not s.system]

        output = f"已安装 {len(skills)} 个技能 (遵循 Agent Skills 规范):\n\n"

        if system_skills:
            output += f"**系统技能 ({len(system_skills)})**:\n"
            for skill in system_skills:
                auto = "自动" if not skill.disable_model_invocation else "手动"
                output += f"- {skill.name} [{auto}] - {skill.description}\n"
            output += "\n"

        if external_skills:
            output += f"**外部技能 ({len(external_skills)})**:\n"
            for skill in external_skills:
                auto = "自动" if not skill.disable_model_invocation else "手动"
                output += f"- {skill.name} [{auto}]\n"
                output += f"  {skill.description}\n\n"

        return output

    def _get_skill_info(self, params: dict) -> str:
        """获取技能详细信息"""
        skill_name = params.get("skill_name")
        if not skill_name:
            return "错误：缺少 skill_name 参数"

        if not hasattr(self.agent, 'skill_registry') or self.agent.skill_registry is None:
            return "技能系统未初始化"

        skill = self.agent.skill_registry.get(skill_name)
        if not skill:
            return f"未找到技能：{skill_name}"

        body = skill.get_body()
        if not body:
            return f"技能 {skill_name} 没有可用的指令内容"

        # 截断过长的内容
        if len(body) > SKILL_MAX_CHARS:
            body = body[:SKILL_MAX_CHARS] + "\n\n[...内容过长已截断...]"

        return f"## {skill_name}\n\n{body}"

    def _run_skill_script(self, params: dict) -> str:
        """运行技能脚本"""
        skill_name = params.get("skill_name")
        script_name = params.get("script_name")
        args = params.get("args", [])

        if not skill_name:
            return "错误：缺少 skill_name 参数"
        if not script_name:
            return "错误：缺少 script_name 参数"

        # 查找技能目录
        skill_path = Path.cwd() / "skills" / skill_name
        if not skill_path.exists():
            return f"技能目录不存在：{skill_name}"

        script_path = skill_path / script_name
        if not script_path.exists():
            return f"脚本不存在：{script_name}"

        # 执行脚本
        import subprocess
        try:
            cmd = ["python3", str(script_path)] + (args if args else [])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(skill_path)
            )
            output = result.stdout
            if result.stderr:
                output += f"\n STDERR: {result.stderr}"
            if result.returncode != 0:
                output = f"脚本执行失败 (返回码：{result.returncode})\n{output}"
            return output
        except subprocess.TimeoutExpired:
            return "脚本执行超时（60 秒）"
        except Exception as e:
            return f"执行脚本时出错：{e}"

    def _get_skill_reference(self, params: dict) -> str:
        """获取技能参考文档"""
        skill_name = params.get("skill_name")
        ref_name = params.get("ref_name", "REFERENCE.md")

        if not skill_name:
            return "错误：缺少 skill_name 参数"

        skill_path = Path.cwd() / "skills" / skill_name
        if not skill_path.exists():
            return f"技能目录不存在：{skill_name}"

        ref_path = skill_path / ref_name
        if not ref_path.exists():
            return f"参考文档不存在：{ref_name}"

        try:
            content = ref_path.read_text(encoding="utf-8")
            return f"## {skill_name} - {ref_name}\n\n{content}"
        except Exception as e:
            return f"读取参考文档失败：{e}"

    async def _install_skill(self, params: dict) -> str:
        """安装技能"""
        skill_name = params.get("skill_name")
        source = params.get("source")

        if not skill_name:
            return "错误：缺少 skill_name 参数"
        if not source:
            return "错误：缺少 source 参数（技能来源 URL 或路径）"

        # TODO: 实现技能安装逻辑
        # 目前仅返回提示信息
        return f"技能安装功能开发中...\n目标：{skill_name}\n来源：{source}"

    def _load_skill(self, params: dict) -> str:
        """加载新技能"""
        skill_path = params.get("skill_path")

        if not skill_path:
            return "错误：缺少 skill_path 参数"

        path = Path(skill_path)
        if not path.exists():
            return f"技能路径不存在：{skill_path}"

        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            return f"SKILL.md 不存在：{skill_path}"

        # TODO: 加载技能到注册中心
        return f"技能加载功能开发中...\n路径：{skill_path}"

    def _reload_skill(self, params: dict) -> str:
        """重新加载技能"""
        skill_name = params.get("skill_name")

        if not skill_name:
            return "错误：缺少 skill_name 参数"

        # TODO: 重新加载技能
        return f"技能重新加载功能开发中...\n技能：{skill_name}"
