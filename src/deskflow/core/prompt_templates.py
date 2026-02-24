"""
Prompt 模板系统

提供:
- Prompt 模板定义
- 变量替换 (支持 {{variable}} 语法)
- 条件渲染
- 模板组合
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTemplate:
    """Prompt 模板"""
    name: str
    template: str
    variables: list[str] = field(default_factory=list)
    description: str = ""

    def render(self, **kwargs: Any) -> str:
        """渲染模板，替换变量"""
        result = self.template

        # 替换 {{variable}} 格式
        for var in self.variables:
            placeholder = "{{" + var + "}}"
            value = kwargs.get(var, "")
            if value is None:
                value = ""
            result = result.replace(placeholder, str(value))

        return result

    def validate(self, **kwargs: Any) -> tuple[bool, list[str]]:
        """验证是否提供了所有必需的变量"""
        missing = []
        for var in self.variables:
            if var not in kwargs:
                missing.append(var)
        return len(missing) == 0, missing


# ==================== 内置模板 ====================

# 系统提示词模板
SYSTEM_PROMPT_TEMPLATE = PromptTemplate(
    name="system_prompt",
    template="""## Identity

{identity}

## System Information

{system_info}

## Available Tools

{tools_section}

## Tools Usage Guide

{tools_guide}

## Core Principles

{core_principles}

## Memory Context

{memory_context}

{custom_sections}""",
    variables=[
        "identity",
        "system_info",
        "tools_section",
        "tools_guide",
        "core_principles",
        "memory_context",
        "custom_sections",
    ],
    description="系统提示词模板",
)

# 用户档案模板
USER_PROFILE_TEMPLATE = PromptTemplate(
    name="user_profile",
    template="""## User Profile

- **Name**: {name}
- **Timezone**: {timezone}
- **Language**: {language}
- **Preferences**:
{preferences}

## Daily Questions

{daily_questions}""",
    variables=[
        "name",
        "timezone",
        "language",
        "preferences",
        "daily_questions",
    ],
    description="用户档案模板",
)

# 记忆上下文模板
MEMORY_CONTEXT_TEMPLATE = PromptTemplate(
    name="memory_context",
    template="""## Relevant Memories

{memories}

## Recent Context

{recent_context}""",
    variables=[
        "memories",
        "recent_context",
    ],
    description="记忆上下文模板",
)

# 工具列表模板
TOOLS_SECTION_TEMPLATE = PromptTemplate(
    name="tools_section",
    template="""## Available Tools

{tools_by_category}

### Usage Notes

- Use `get_tool_info(tool_name)` to get detailed parameter definitions
- All tools can be called directly by name
- For complex tasks, consider combining multiple tools""",
    variables=[
        "tools_by_category",
    ],
    description="工具列表模板",
)

# 任务指令模板
TASK_INSTRUCTION_TEMPLATE = PromptTemplate(
    name="task_instruction",
    template="""## Current Task

**Description**: {task_description}

**Constraints**: {constraints}

**Success Criteria**: {success_criteria}

**Available Resources**: {resources}

Please complete this task step by step.""",
    variables=[
        "task_description",
        "constraints",
        "success_criteria",
        "resources",
    ],
    description="任务指令模板",
)

# 编译管线模板 (v2)
COMPILED_SYSTEM_TEMPLATE = PromptTemplate(
    name="compiled_system",
    template="""# Agent System Prompt

## Core Identity
{identity_compiled}

## Environment
{environment_section}

## Capabilities
{capabilities_section}

## Context
{context_section}

## Instructions
{instructions_section}""",
    variables=[
        "identity_compiled",
        "environment_section",
        "capabilities_section",
        "context_section",
        "instructions_section",
    ],
    description="编译后的系统提示词模板 (v2)",
)


# ==================== 模板管理器 ====================

class PromptTemplateManager:
    """
    Prompt 模板管理器

    管理模板注册、加载和渲染
    """

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._render_hooks: list[Callable[[str, dict], str]] = []

        # 注册内置模板
        self._register_builtins()

    def _register_builtins(self) -> None:
        """注册内置模板"""
        builtins = [
            SYSTEM_PROMPT_TEMPLATE,
            USER_PROFILE_TEMPLATE,
            MEMORY_CONTEXT_TEMPLATE,
            TOOLS_SECTION_TEMPLATE,
            TASK_INSTRUCTION_TEMPLATE,
            COMPILED_SYSTEM_TEMPLATE,
        ]
        for template in builtins:
            self.register(template)

    def register(self, template: PromptTemplate) -> None:
        """注册模板"""
        self._templates[template.name] = template
        logger.debug(f"[PromptTemplateManager] Registered template: {template.name}")

    def get(self, name: str) -> PromptTemplate | None:
        """获取模板"""
        return self._templates.get(name)

    def render(self, name: str, **kwargs: Any) -> str | None:
        """渲染模板"""
        template = self.get(name)
        if not template:
            logger.warning(f"[PromptTemplateManager] Template not found: {name}")
            return None

        result = template.render(**kwargs)

        # 应用渲染钩子
        for hook in self._render_hooks:
            try:
                result = hook(result, kwargs)
            except Exception as e:
                logger.warning(f"[PromptTemplateManager] Render hook error: {e}")

        return result

    def register_render_hook(self, hook: Callable[[str, dict], str]) -> None:
        """注册渲染钩子（用于后处理）"""
        self._render_hooks.append(hook)

    def list_templates(self) -> list[str]:
        """列出所有模板名称"""
        return list(self._templates.keys())


# ==================== 变量提取器 ====================

def extract_variables(template: str) -> list[str]:
    """从模板字符串中提取变量名"""
    pattern = r"\{\{(\w+)\}\}"
    matches = re.findall(pattern, template)
    return list(set(matches))  # 去重


def create_template(name: str, template: str, description: str = "") -> PromptTemplate:
    """快速创建模板"""
    variables = extract_variables(template)
    return PromptTemplate(
        name=name,
        template=template,
        variables=variables,
        description=description,
    )


# ==================== 条件渲染 ====================

def conditional_render(condition: bool, content: str) -> str:
    """条件渲染"""
    return content if condition else ""


def optional_section(
    name: str,
    content: str,
    wrapper: str = "## {name}\n\n{content}",
) -> str:
    """可选段落渲染"""
    if not content or not content.strip():
        return ""
    return wrapper.format(name=name, content=content)


# ==================== 全局单例 ====================

_template_manager: PromptTemplateManager | None = None


def get_template_manager() -> PromptTemplateManager:
    """获取模板管理器单例"""
    global _template_manager
    if _template_manager is None:
        _template_manager = PromptTemplateManager()
    return _template_manager


def reset_template_manager() -> None:
    """重置模板管理器（用于测试）"""
    global _template_manager
    _template_manager = None
