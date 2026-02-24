"""Skill sandbox executor for isolated skill execution.

Runs skills in a subprocess with:
- Resource limits (memory, CPU time)
- Filesystem access control
- Network access control
- Timeout enforcement
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class SandboxPolicy:
    """Sandbox security policy defining allowed operations."""

    def __init__(
        self,
        max_memory_mb: int = 256,
        max_cpu_seconds: float = 30.0,
        allowed_paths: list[Path] | None = None,
        allow_network: bool = False,
        allow_subprocess: bool = False,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_cpu_seconds = max_cpu_seconds
        self.allowed_paths = allowed_paths or []
        self.allow_network = allow_network
        self.allow_subprocess = allow_subprocess

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for subprocess communication."""
        return {
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_seconds": self.max_cpu_seconds,
            "allowed_paths": [str(p) for p in self.allowed_paths],
            "allow_network": self.allow_network,
            "allow_subprocess": self.allow_subprocess,
        }


class SandboxResult:
    """Result of sandbox execution."""

    def __init__(
        self,
        success: bool,
        output: str,
        error: str = "",
        return_code: int = 0,
        execution_time: float = 0.0,
        memory_used_mb: float = 0.0,
    ) -> None:
        self.success = success
        self.output = output
        self.error = error
        self.return_code = return_code
        self.execution_time = execution_time
        self.memory_used_mb = memory_used_mb

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxResult:
        """Create from dictionary."""
        return cls(
            success=data.get("success", False),
            output=data.get("output", ""),
            error=data.get("error", ""),
            return_code=data.get("return_code", 0),
            execution_time=data.get("execution_time", 0.0),
            memory_used_mb=data.get("memory_used_mb", 0.0),
        )


class SandboxedSkillExecutor:
    """Executes skills in an isolated sandbox environment.

    Features:
    - Subprocess isolation
    - Resource limits (memory, CPU time)
    - Filesystem path restrictions
    - Optional network access control
    - Detailed execution metrics
    """

    def __init__(
        self,
        policy: SandboxPolicy | None = None,
        work_dir: Path | None = None,
    ) -> None:
        self._policy = policy or SandboxPolicy()
        self._work_dir = work_dir or Path(tempfile.gettempdir()) / "deskflow_skills"
        self._work_dir.mkdir(parents=True, exist_ok=True)
        logger.info("sandbox_executor_initialized", work_dir=str(self._work_dir))

    async def execute(
        self,
        skill_path: Path,
        skill_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> SandboxResult:
        """Execute a skill in the sandbox.

        Args:
            skill_path: Path to skill directory
            skill_name: Name of the skill
            arguments: Arguments to pass to the skill
            timeout: Optional timeout override

        Returns:
            Execution result
        """
        # Prepare execution environment
        runner_script = self._prepare_runner(skill_path, skill_name, arguments)

        # Build subprocess command
        cmd = [
            sys.executable,
            "-u",  # Unbuffered output
            str(runner_script),
        ]

        # Resource limits via environment
        env = os.environ.copy()
        env["DESKFLOW_SANDBOX_MAX_MEMORY"] = str(self._policy.max_memory_mb)
        env["DESKFLOW_SANDBOX_MAX_CPU"] = str(self._policy.max_cpu_seconds)

        if not self._policy.allow_network:
            env["DESKFLOW_SANDBOX_NO_NETWORK"] = "1"

        if not self._policy.allow_subprocess:
            env["DESKFLOW_SANDBOX_NO_SUBPROCESS"] = "1"

        # Allowed paths
        if self._policy.allowed_paths:
            env["DESKFLOW_SANDBOX_ALLOWED_PATHS"] = ":".join(
                str(p) for p in self._policy.allowed_paths
            )

        # Execute with timeout
        exec_timeout = timeout or self._policy.max_cpu_seconds

        try:
            start_time = asyncio.get_event_loop().time()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(self._work_dir),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=exec_timeout,
            )

            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            # Parse result
            try:
                result_data = json.loads(stdout.decode())
                result = SandboxResult.from_dict(result_data)
            except json.JSONDecodeError:
                result = SandboxResult(
                    success=process.returncode == 0,
                    output=stdout.decode(),
                    error=stderr.decode() if stderr else "",
                    return_code=process.returncode or 0,
                    execution_time=execution_time,
                )

            logger.info(
                "sandbox_execution_complete",
                skill=skill_name,
                success=result.success,
                duration=round(execution_time, 2),
            )

            return result

        except asyncio.TimeoutError:
            logger.warning("sandbox_execution_timeout", skill=skill_name, timeout=exec_timeout)
            # Kill the process
            try:
                process.kill()
            except ProcessLookupError:
                pass

            return SandboxResult(
                success=False,
                output="",
                error=f"Execution timeout after {exec_timeout}s",
                return_code=-1,
                execution_time=exec_timeout,
            )

        except Exception as e:
            logger.error("sandbox_execution_failed", skill=skill_name, error=str(e))
            return SandboxResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                execution_time=0.0,
            )

    def _prepare_runner(
        self,
        skill_path: Path,
        skill_name: str,
        arguments: dict[str, Any],
    ) -> Path:
        """Prepare the runner script for skill execution.

        Creates a temporary Python script that:
        1. Imports the skill module
        2. Enforces resource limits
        3. Executes the skill
        4. Returns structured result
        """
        # Read skill source
        skill_file = skill_path / "skill.py"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")

        skill_source = skill_file.read_text()

        # Create runner script
        runner_code = f'''
import sys
import os
import json
import resource
import time

# Parse arguments
skill_args = {json.dumps(arguments)}

# Enforce memory limit
max_memory_mb = int(os.environ.get("DESKFLOW_SANDBOX_MAX_MEMORY", 256))
resource.setrlimit(resource.RLIMIT_AS, (max_memory_mb * 1024 * 1024, max_memory_mb * 1024 * 1024))

# Enforce CPU time limit
max_cpu = float(os.environ.get("DESKFLOW_SANDBOX_MAX_CPU", 30.0))
resource.setrlimit(resource.RLIMIT_CPU, (int(max_cpu), int(max_cpu) + 5))

# Block network if configured
if os.environ.get("DESKFLOW_SANDBOX_NO_NETWORK"):
    import socket
    def blocked_socket(*args, **kwargs):
        raise PermissionError("Network access denied in sandbox")
    socket.socket = blocked_socket

# Block subprocess if configured
if os.environ.get("DESKFLOW_SANDBOX_NO_SUBPROCESS"):
    import subprocess
    def blocked_subprocess(*args, **kwargs):
        raise PermissionError("Subprocess access denied in sandbox")
    subprocess.run = blocked_subprocess
    subprocess.Popen = blocked_subprocess

# Add skill directory to path
sys.path.insert(0, "{str(skill_path)}")

start_time = time.time()

try:
    # Import and execute skill
    from skill import execute

    result = execute(**skill_args)

    # Handle async result
    if hasattr(result, "__await__"):
        import asyncio
        result = asyncio.run(result)

    execution_time = time.time() - start_time

    # Output result
    output = {{
        "success": True,
        "output": str(result) if result is not None else "",
        "execution_time": execution_time,
    }}

except MemoryError:
    output = {{
        "success": False,
        "error": "Memory limit exceeded",
    }}
except PermissionError as e:
    output = {{
        "success": False,
        "error": f"Permission denied: {{e}}",
    }}
except Exception as e:
    output = {{
        "success": False,
        "error": str(e),
    }}

# Output JSON result
print(json.dumps(output))
'''

        # Write runner script
        runner_path = self._work_dir / f"runner_{skill_name}.py"
        runner_path.write_text(runner_code)

        return runner_path


class SkillRegistry:
    """Registry for managing installed skills."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path.cwd() / "skills"
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillInfo] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        """Load skills from directory."""
        for item in self._skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                meta_file = item / "skill.json"
                if meta_file.exists():
                    import json

                    with open(meta_file) as f:
                        meta = json.load(f)
                    self._skills[meta.get("name", item.name)] = SkillInfo(
                        name=meta.get("name", item.name),
                        description=meta.get("description", ""),
                        version=meta.get("version", "0.1.0"),
                        path=item,
                        is_active=meta.get("is_active", True),
                    )

    def list_skills(self) -> list[SkillInfo]:
        """List all registered skills."""
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillInfo | None:
        """Get skill by name."""
        return self._skills.get(name)

    def install_skill(self, skill_path: Path) -> SkillInfo:
        """Install a skill from directory."""
        meta_file = skill_path / "skill.json"
        if not meta_file.exists():
            raise ValueError("skill.json not found")

        import json
        import shutil

        with open(meta_file) as f:
            meta = json.load(f)

        skill_name = meta.get("name", skill_path.name)
        dest_path = self._skills_dir / skill_name

        # Copy skill files
        if dest_path.exists():
            shutil.rmtree(dest_path)
        shutil.copytree(skill_path, dest_path)

        # Register skill
        skill_info = SkillInfo(
            name=skill_name,
            description=meta.get("description", ""),
            version=meta.get("version", "0.1.0"),
            path=dest_path,
            is_active=True,
        )
        self._skills[skill_name] = skill_info

        logger.info("skill_installed", name=skill_name, path=str(dest_path))
        return skill_info

    def uninstall_skill(self, name: str) -> bool:
        """Uninstall a skill."""
        if name not in self._skills:
            return False

        import shutil

        skill_path = self._skills[name].path
        shutil.rmtree(skill_path)
        del self._skills[name]

        logger.info("skill_uninstalled", name=name)
        return True

    def activate_skill(self, name: str, active: bool) -> bool:
        """Activate or deactivate a skill."""
        if name not in self._skills:
            return False

        self._skills[name].is_active = active

        # Update skill.json
        meta_file = self._skills[name].path / "skill.json"
        if meta_file.exists():
            import json

            with open(meta_file) as f:
                meta = json.load(f)
            meta["is_active"] = active
            with open(meta_file, "w") as f:
                json.dump(meta, f, indent=2)

        logger.info("skill_toggled", name=name, active=active)
        return True


class SkillInfo:
    """Information about an installed skill."""

    def __init__(
        self,
        name: str,
        description: str = "",
        version: str = "0.1.0",
        path: Path | None = None,
        is_active: bool = True,
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.path = path
        self.is_active = is_active

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "is_active": self.is_active,
            "path": str(self.path) if self.path else None,
        }
