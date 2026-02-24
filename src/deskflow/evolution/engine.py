"""Self-evolution system for automatic improvement and error resolution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class SkillGenerator:
    """Automatic skill generator based on error analysis.

    Features:
    - Analyze error patterns
    - Generate Python skill code
    - Create skill configuration
    - Validate generated code
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path.cwd() / "skills" / "auto_generated"
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._llm_client = None

    def set_llm_client(self, llm_client) -> None:
        """Set LLM client for code generation."""
        self._llm_client = llm_client

    def generate_skill_code(
        self,
        error_type: str,
        error_message: str,
        suggested_fix: dict[str, str],
    ) -> str:
        """Generate Python skill code to fix the error.

        Args:
            error_type: Type of error
            error_message: Error description
            suggested_fix: Suggested fix with skill name and description

        Returns:
            Generated Python code string
        """
        skill_name = suggested_fix.get("skill", "fix_skill")
        description = suggested_fix.get("description", "Auto-generated fix skill")

        # Generate skill code template
        code = f'''"""Auto-generated skill: {skill_name}

Generated at: {datetime.now().isoformat()}
Purpose: {description}
Error Type: {error_type}
Error Message: {error_message[:200]}
"""

from __future__ import annotations

from typing import Any

from deskflow.skills.base import BaseSkill


class {self._to_class_name(skill_name)}(BaseSkill):
    """{description}"""

    name = "{skill_name}"
    description = "{description}"
    version = "0.1.0"

    def __init__(self) -> None:
        super().__init__()
        self._error_count = 0

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the skill.

        Args:
            **kwargs: Skill arguments

        Returns:
            Execution result
        """
        try:
            self._error_count += 1
            result = await self._fix_logic(**kwargs)
            return {{
                "success": True,
                "skill": self.name,
                "result": result,
            }}
        except Exception as e:
            return {{
                "success": False,
                "skill": self.name,
                "error": str(e),
            }}

    async def _fix_logic(self, **kwargs: Any) -> Any:
        """Implement the fix logic here.

        TODO: Customize this method based on specific error requirements.
        """
        # Default implementation - should be customized
        return {{
            "message": "Skill executed",
            "error_type": "{error_type}",
            "execution_count": self._error_count,
        }}


# Factory function for skill registry
def create_skill():
    return {self._to_class_name(skill_name)}()
'''
        return code

    def _to_class_name(self, skill_name: str) -> str:
        """Convert skill name to class name (snake_case -> PascalCase)."""
        parts = skill_name.replace("-", "_").split("_")
        return "".join(p.capitalize() for p in parts) + "Skill"

    def save_skill(
        self,
        code: str,
        skill_name: str,
        config: dict[str, Any] | None = None,
    ) -> Path:
        """Save generated skill to disk.

        Args:
            code: Python code string
            skill_name: Skill name
            config: Optional skill configuration

        Returns:
            Path to saved skill directory
        """
        skill_dir = self._skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Save main skill code
        skill_file = skill_dir / f"{skill_name}.py"
        with open(skill_file, "w") as f:
            f.write(code)

        # Save configuration
        skill_config = config or {
            "name": skill_name,
            "enabled": True,
            "auto_generated": True,
            "created_at": datetime.now().isoformat(),
        }
        config_file = skill_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(skill_config, f, indent=2)

        # Save __init__.py for module import
        init_file = skill_dir / "__init__.py"
        with open(init_file, "w") as f:
            f.write(f'from .{skill_name} import create_skill\n')

        logger.info("skill_generated", skill=skill_name, path=str(skill_dir))
        return skill_dir

    def validate_skill(self, skill_dir: Path) -> bool:
        """Validate generated skill structure.

        Args:
            skill_dir: Path to skill directory

        Returns:
            True if valid
        """
        required_files = ["__init__.py", "config.json"]

        for file in required_files:
            if not (skill_dir / file).exists():
                logger.warning("skill_validation_failed", missing=file)
                return False

        # Check if the Python skill file exists
        py_files = list(skill_dir.glob("*.py"))
        if not py_files:
            logger.warning("skill_validation_failed", missing="*.py")
            return False

        # Basic syntax validation
        main_py = py_files[0]
        try:
            code = main_py.read_text()
            compile(code, str(main_py), "exec")
            logger.info("skill_syntax_valid", skill=skill_dir.name)
        except SyntaxError as e:
            logger.warning("skill_syntax_error", skill=skill_dir.name, error=str(e))
            return False

        logger.info("skill_validated", skill=skill_dir.name)
        return True


class SelfCheckResult:
    """Result of daily self-check."""

    def __init__(
        self,
        healthy: bool,
        checks: dict[str, bool],
        issues: list[str],
        recommendations: list[str],
    ) -> None:
        self.healthy = healthy
        self.checks = checks
        self.issues = issues
        self.recommendations = recommendations

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "healthy": self.healthy,
            "checks": self.checks,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "timestamp": datetime.now().isoformat(),
        }


class EvolutionEngine:
    """Self-evolution engine for automatic improvement.

    Features:
    - Daily self-check
    - Error log analysis
    - Automatic skill generation for error resolution
    - Performance trend tracking
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or Path.cwd() / "data" / "evolution"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._error_log: list[ErrorEntry] = []
        self._check_history: list[SelfCheckResult] = []

    def record_error(
        self,
        error_type: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record an error for later analysis."""
        entry = ErrorEntry(
            timestamp=datetime.now(),
            error_type=error_type,
            error_message=error_message,
            context=context or {},
        )
        self._error_log.append(entry)
        logger.debug("error_recorded", type=error_type, message=error_message[:100])

    async def run_self_check(self) -> SelfCheckResult:
        """Run daily self-check."""
        checks = {
            "memory": await self._check_memory(),
            "tools": await self._check_tools(),
            "llm": await self._check_llm(),
            "disk": self._check_disk(),
        }

        issues = []
        recommendations = []

        if not checks["memory"]:
            issues.append("Memory system may need attention")
            recommendations.append("Consider running memory consolidation")

        if not checks["tools"]:
            issues.append("Some tools are not responding")
            recommendations.append("Check tool timeout settings")

        if not checks["llm"]:
            issues.append("LLM connection unstable")
            recommendations.append("Verify API key and endpoint")

        if not checks["disk"]:
            issues.append("Disk space low")
            recommendations.append("Clean up old logs and cache")

        healthy = all(checks.values())

        result = SelfCheckResult(
            healthy=healthy,
            checks=checks,
            issues=issues,
            recommendations=recommendations,
        )

        self._check_history.append(result)
        self._save_check_result(result)

        logger.info("self_check_complete", healthy=healthy, issues=len(issues))
        return result

    async def _check_memory(self) -> bool:
        """Check memory system health."""
        # Placeholder - would check actual memory system
        return True

    async def _check_tools(self) -> bool:
        """Check tools system health."""
        # Placeholder - would test tool execution
        return True

    async def _check_llm(self) -> bool:
        """Check LLM connection health."""
        # Placeholder - would test LLM connection
        return True

    def _check_disk(self) -> bool:
        """Check disk space."""
        import psutil

        disk = psutil.disk_usage("/")
        return disk.percent < 90

    def _save_check_result(self, result: SelfCheckResult) -> None:
        """Save check result to file."""
        log_file = self._data_dir / "self_check_log.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

    def analyze_errors(self) -> ErrorAnalysis:
        """Analyze recorded errors for patterns."""
        if not self._error_log:
            return ErrorAnalysis(patterns=[], root_causes=[], suggested_fixes=[])

        # Group by type
        by_type: dict[str, list[ErrorEntry]] = {}
        for entry in self._error_log:
            if entry.error_type not in by_type:
                by_type[entry.error_type] = []
            by_type[entry.error_type].append(entry)

        # Find patterns
        patterns = []
        for error_type, entries in by_type.items():
            if len(entries) >= 3:  # Recurring error
                patterns.append({
                    "type": error_type,
                    "count": len(entries),
                    "message": entries[0].error_message[:200],
                })

        # Suggest fixes
        suggested_fixes = []
        for pattern in patterns:
            fix = self._suggest_fix(pattern["type"])
            if fix:
                suggested_fixes.append(fix)

        return ErrorAnalysis(
            patterns=patterns,
            root_causes=self._identify_root_causes(by_type),
            suggested_fixes=suggested_fixes,
        )

    def _suggest_fix(self, error_type: str) -> dict[str, str] | None:
        """Suggest fix for error type."""
        fixes = {
            "LLMRateLimitError": {
                "skill": "rate_limit_handler",
                "description": "Add exponential backoff for LLM requests",
            },
            "ToolExecutionError": {
                "skill": "tool_retry",
                "description": "Add retry logic with fallback for tools",
            },
            "MemoryRetrievalError": {
                "skill": "memory_optimizer",
                "description": "Optimize memory queries and add caching",
            },
        }
        return fixes.get(error_type)

    def _identify_root_causes(
        self,
        by_type: dict[str, list[ErrorEntry]],
    ) -> list[str]:
        """Identify root causes from error patterns."""
        causes = []

        for error_type, entries in by_type.items():
            if len(entries) >= 5:
                causes.append(f"Recurring {error_type} - may need architectural fix")

        return causes

    def generate_fix_skill(
        self,
        error_type: str,
        error_message: str,
        skill_name: str | None = None,
    ) -> Path | None:
        """Generate a skill to fix the specified error.

        Args:
            error_type: Type of error to fix
            error_message: Error description
            skill_name: Optional custom skill name

        Returns:
            Path to generated skill directory, or None if no fix available
        """
        # Get suggested fix
        suggested_fix = self._suggest_fix(error_type)
        if not suggested_fix:
            # Generate default fix if no predefined fix exists
            suggested_fix = {
                "skill": skill_name or f"fix_{error_type.lower().replace('error', '')}",
                "description": f"Handle {error_type} errors",
            }

        # Create skill generator if needed
        if not hasattr(self, "_skill_generator"):
            self._skill_generator = SkillGenerator()

        # Generate code
        code = self._skill_generator.generate_skill_code(
            error_type=error_type,
            error_message=error_message,
            suggested_fix=suggested_fix,
        )

        # Save skill
        skill_path = self._skill_generator.save_skill(
            code=code,
            skill_name=suggested_fix["skill"],
            config={
                "name": suggested_fix["skill"],
                "description": suggested_fix["description"],
                "enabled": True,
                "auto_generated": True,
                "created_at": datetime.now().isoformat(),
                "error_type": error_type,
            },
        )

        # Validate skill
        if self._skill_generator.validate_skill(skill_path):
            logger.info(
                "skill_generated_success",
                skill=suggested_fix["skill"],
                path=str(skill_path),
            )
            return skill_path
        else:
            logger.warning("skill_generated_invalid", skill=suggested_fix["skill"])
            return None

    def generate_skills_for_recurring_errors(
        self,
        min_occurrences: int = 3,
    ) -> list[Path]:
        """Generate skills for all recurring errors.

        Args:
            min_occurrences: Minimum occurrences to consider as recurring

        Returns:
            List of generated skill paths
        """
        analysis = self.analyze_errors()
        generated_paths = []

        for pattern in analysis.patterns:
            if pattern["count"] >= min_occurrences:
                # Find corresponding error entry for full message
                error_entry = next(
                    (e for e in self._error_log if e.error_type == pattern["type"]),
                    None,
                )
                if error_entry:
                    path = self.generate_fix_skill(
                        error_type=pattern["type"],
                        error_message=error_entry.error_message,
                    )
                    if path:
                        generated_paths.append(path)

        return generated_paths

    def get_stats(self) -> dict[str, Any]:
        """Get evolution statistics."""
        return {
            "total_errors": len(self._error_log),
            "self_checks": len(self._check_history),
            "last_check": (
                self._check_history[-1].to_dict() if self._check_history else None
            ),
        }


class ErrorEntry:
    """Recorded error entry."""

    def __init__(
        self,
        timestamp: datetime,
        error_type: str,
        error_message: str,
        context: dict[str, Any],
    ) -> None:
        self.timestamp = timestamp
        self.error_type = error_type
        self.error_message = error_message
        self.context = context

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.error_type,
            "message": self.error_message,
            "context": self.context,
        }


class ErrorAnalysis:
    """Result of error analysis."""

    def __init__(
        self,
        patterns: list[dict[str, Any]],
        root_causes: list[str],
        suggested_fixes: list[dict[str, str]],
    ) -> None:
        self.patterns = patterns
        self.root_causes = root_causes
        self.suggested_fixes = suggested_fixes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "patterns": self.patterns,
            "root_causes": self.root_causes,
            "suggested_fixes": self.suggested_fixes,
        }
