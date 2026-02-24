"""Reasoning engine for complex task planning and problem solving.

Provides:
- Task decomposition into sub-tasks
- Dependency analysis
- Step-by-step reasoning
- Multi-step planning
- Goal-oriented reasoning
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class ReasoningType(str, Enum):
    """Type of reasoning strategy."""

    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ABDUCTIVE = "abductive"
    ANALOGICAL = "analogical"
    CAUSAL = "causal"
    ANALYTICAL = "analytical"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class ReasoningStep:
    """Single step in a reasoning chain."""

    step_number: int
    reasoning_type: ReasoningType
    premise: str
    inference: str
    confidence: float = 1.0
    source: str | None = None


@dataclass
class SubTask:
    """Sub-task in a plan."""

    id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    estimated_steps: int = 1
    actual_steps: int = 0


@dataclass
class ReasoningChain:
    """Chain of reasoning steps leading to a conclusion."""

    goal: str
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str | None = None
    overall_conffidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Plan:
    """Multi-step plan for achieving a goal."""

    goal: str
    subtasks: list[SubTask] = field(default_factory=list)
    status: str = "draft"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return all(t.status == TaskStatus.COMPLETED for t in self.subtasks)

    @property
    def progress(self) -> float:
        if not self.subtasks:
            return 0.0
        completed = sum(1 for t in self.subtasks if t.status == TaskStatus.COMPLETED)
        return completed / len(self.subtasks) * 100

    def get_next_task(self) -> SubTask | None:
        completed_ids = {t.id for t in self.subtasks if t.status == TaskStatus.COMPLETED}
        for task in self.subtasks:
            if task.status == TaskStatus.PENDING:
                if all(dep_id in completed_ids for dep_id in task.dependencies):
                    return task
        return None

    def get_blocked_tasks(self) -> list[SubTask]:
        failed_ids = {t.id for t in self.subtasks if t.status == TaskStatus.FAILED}
        blocked = []
        for task in self.subtasks:
            if task.status == TaskStatus.PENDING:
                if any(dep_id in failed_ids for dep_id in task.dependencies):
                    blocked.append(task)
        return blocked


@dataclass
class ReasoningResult:
    """Result of a reasoning operation."""

    success: bool
    reasoning_chain: ReasoningChain | None = None
    plan: Plan | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskDecomposer:
    """Decompose complex tasks into manageable sub-tasks."""

    TASK_PATTERNS: dict[str, list[str]] = {
        "research": [
            "Define research question",
            "Gather relevant information",
            "Analyze sources",
            "Synthesize findings",
            "Document conclusions",
        ],
        "coding": [
            "Understand requirements",
            "Design solution approach",
            "Implement code",
            "Test functionality",
            "Review and refactor",
        ],
        "debugging": [
            "Reproduce the issue",
            "Identify root cause",
            "Develop fix strategy",
            "Implement fix",
            "Verify resolution",
        ],
        "analysis": [
            "Define analysis scope",
            "Collect data",
            "Process and clean data",
            "Analyze patterns",
            "Report insights",
        ],
        "writing": [
            "Outline structure",
            "Draft content",
            "Review and revise",
            "Edit for clarity",
            "Final polish",
        ],
    }

    def decompose(
        self,
        task: str,
        max_depth: int = 3,
        context: dict[str, Any] | None = None,
    ) -> list[SubTask]:
        task_lower = task.lower()
        matched_pattern = None

        for pattern_name, steps in self.TASK_PATTERNS.items():
            if pattern_name in task_lower:
                matched_pattern = steps
                break

        if matched_pattern:
            return self._create_tasks_from_steps(task, matched_pattern)
        else:
            return self._generic_decompose(task, max_depth)

    def _create_tasks_from_steps(
        self, goal: str, steps: list[str]
    ) -> list[SubTask]:
        tasks = []
        prev_id = None

        for i, step in enumerate(steps):
            task_id = f"step_{i + 1}"
            task = SubTask(
                id=task_id,
                name=step,
                description=f"{step} as part of: {goal}",
                dependencies=[prev_id] if prev_id else [],
                estimated_steps=1,
            )
            tasks.append(task)
            prev_id = task_id

        return tasks

    def _generic_decompose(self, task: str, max_depth: int) -> list[SubTask]:
        return [
            SubTask(
                id="plan",
                name="Plan approach",
                description=f"Plan how to: {task}",
                dependencies=[],
            ),
            SubTask(
                id="execute",
                name="Execute plan",
                description="Carry out the planned approach",
                dependencies=["plan"],
            ),
            SubTask(
                id="verify",
                name="Verify results",
                description="Confirm the task was completed successfully",
                dependencies=["execute"],
            ),
        ]


class ReasoningEngine:
    """Multi-step reasoning engine for complex problem solving."""

    def __init__(
        self,
        working_dir: Path | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._working_dir = working_dir or Path.cwd() / "data" / "reasoning"
        self._working_dir.mkdir(parents=True, exist_ok=True)
        self._llm_client = llm_client
        self._decomposer = TaskDecomposer()
        self._active_plans: dict[str, Plan] = {}
        self._reasoning_history: list[ReasoningChain] = []

    def reason(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        use_llm: bool = False,
    ) -> ReasoningResult:
        logger.info("reasoning_start", goal=goal)

        try:
            analysis = self._analyze_goal(goal, context)
            chain = self._create_reasoning_chain(goal, analysis, use_llm)
            plan = self._generate_plan(goal, analysis, context)

            self._reasoning_history.append(chain)
            if plan:
                self._active_plans[plan.goal] = plan

            logger.info(
                "reasoning_complete",
                goal=goal,
                steps=len(chain.steps),
                subtasks=len(plan.subtasks) if plan else 0,
            )

            return ReasoningResult(
                success=True,
                reasoning_chain=chain,
                plan=plan,
                metadata={"analysis": analysis},
            )

        except Exception as e:
            logger.error("reasoning_failed", goal=goal, error=str(e))
            return ReasoningResult(success=False, error=str(e))

    def _analyze_goal(
        self, goal: str, context: dict[str, Any] | None
    ) -> dict[str, Any]:
        analysis = {
            "goal": goal,
            "complexity": "medium",
            "estimated_steps": 3,
            "requires_tools": False,
            "requires_research": False,
            "requires_creativity": False,
        }

        goal_lower = goal.lower()
        tool_keywords = ["execute", "run", "create file", "write", "search", "fetch", "download", "install", "build"]
        if any(kw in goal_lower for kw in tool_keywords):
            analysis["requires_tools"] = True
            analysis["complexity"] = "medium"

        research_keywords = ["research", "analyze", "investigate", "find information", "learn about", "understand"]
        if any(kw in goal_lower for kw in research_keywords):
            analysis["requires_research"] = True
            analysis["estimated_steps"] = 5

        creative_keywords = ["write", "create", "design", "compose", "generate", "brainstorm", "imagine"]
        if any(kw in goal_lower for kw in creative_keywords):
            analysis["requires_creativity"] = True

        if len(goal.split()) > 20:
            analysis["complexity"] = "complex"
            analysis["estimated_steps"] = 5

        if context:
            analysis["context"] = context

        return analysis

    def _create_reasoning_chain(
        self, goal: str, analysis: dict[str, Any], use_llm: bool
    ) -> ReasoningChain:
        chain = ReasoningChain(goal=goal)

        chain.steps.append(ReasoningStep(
            step_number=1,
            reasoning_type=ReasoningType.ABDUCTIVE,
            premise=f"Goal stated: {goal}",
            inference="Understanding what needs to be accomplished",
            confidence=1.0,
        ))

        complexity = analysis.get("complexity", "medium")
        chain.steps.append(ReasoningStep(
            step_number=2,
            reasoning_type=ReasoningType.ANALYTICAL,
            premise=f"Goal complexity: {complexity}",
            inference=f"Estimated {analysis.get('estimated_steps', 3)} steps needed",
            confidence=0.9,
        ))

        if analysis.get("requires_tools"):
            chain.steps.append(ReasoningStep(
                step_number=3,
                reasoning_type=ReasoningType.DEDUCTIVE,
                premise="Task requires tool usage",
                inference="Will need to execute tools and handle their outputs",
                confidence=0.95,
            ))
        elif analysis.get("requires_research"):
            chain.steps.append(ReasoningStep(
                step_number=3,
                reasoning_type=ReasoningType.INDUCTIVE,
                premise="Task requires information gathering",
                inference="Will need to search, analyze, and synthesize information",
                confidence=0.9,
            ))
        else:
            chain.steps.append(ReasoningStep(
                step_number=3,
                reasoning_type=ReasoningType.DEDUCTIVE,
                premise="Task is primarily analytical",
                inference="Can proceed with direct reasoning",
                confidence=0.95,
            ))

        if chain.steps:
            chain.overall_conffidence = sum(s.confidence for s in chain.steps) / len(chain.steps)

        chain.conclusion = f"Ready to execute: {goal}"
        return chain

    def _generate_plan(
        self, goal: str, analysis: dict[str, Any], context: dict[str, Any] | None
    ) -> Plan | None:
        subtasks = self._decomposer.decompose(goal, context=context)
        if not subtasks:
            return None

        plan = Plan(goal=goal, subtasks=subtasks)
        logger.info("plan_generated", goal=goal, subtask_count=len(subtasks))
        return plan

    def update_task_status(
        self,
        plan_id: str,
        task_id: str,
        status: TaskStatus,
        result: str | None = None,
        error: str | None = None,
    ) -> bool:
        plan = self._active_plans.get(plan_id)
        if not plan:
            logger.warning("plan_not_found", plan_id=plan_id)
            return False

        for task in plan.subtasks:
            if task.id == task_id:
                task.status = status
                task.result = result
                task.error = error
                task.actual_steps += 1

                if plan.is_complete:
                    plan.status = "completed"
                    plan.completed_at = datetime.now()
                    logger.info("plan_completed", plan_id=plan_id)

                blocked = self.get_blocked_tasks(plan_id)
                for blocked_task in blocked:
                    blocked_task.status = TaskStatus.BLOCKED
                    logger.warning(
                        "task_blocked",
                        plan_id=plan_id,
                        task_id=blocked_task.id,
                        reason="dependency_failed",
                    )

                return True

        logger.warning("task_not_found", plan_id=plan_id, task_id=task_id)
        return False

    def get_plan(self, plan_id: str) -> Plan | None:
        return self._active_plans.get(plan_id)

    def get_blocked_tasks(self, plan_id: str) -> list[SubTask]:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return []
        return plan.get_blocked_tasks()

    def get_next_task(self, plan_id: str) -> SubTask | None:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None
        return plan.get_next_task()

    def list_active_plans(self) -> list[str]:
        return list(self._active_plans.keys())

    def get_plan_status(self, plan_id: str) -> dict[str, Any] | None:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None

        return {
            "goal": plan.goal,
            "status": plan.status,
            "progress": plan.progress,
            "total_tasks": len(plan.subtasks),
            "completed_tasks": sum(1 for t in plan.subtasks if t.status == TaskStatus.COMPLETED),
            "failed_tasks": sum(1 for t in plan.subtasks if t.status == TaskStatus.FAILED),
            "blocked_tasks": sum(1 for t in plan.subtasks if t.status == TaskStatus.BLOCKED),
            "pending_tasks": sum(1 for t in plan.subtasks if t.status == TaskStatus.PENDING),
        }

    def save_plan_to_file(self, plan: Plan, output_path: Path | None = None) -> Path:
        if output_path is None:
            output_path = self._working_dir / f"plan_{plan.goal.replace(' ', '_')[:30]}.json"

        plan_data = {
            "goal": plan.goal,
            "status": plan.status,
            "created_at": plan.created_at.isoformat(),
            "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
            "subtasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "status": t.status.value,
                    "dependencies": t.dependencies,
                    "result": t.result,
                    "error": t.error,
                    "estimated_steps": t.estimated_steps,
                    "actual_steps": t.actual_steps,
                }
                for t in plan.subtasks
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False)

        logger.info("plan_saved", path=str(output_path))
        return output_path

    def export_reasoning_history(self, output_path: Path | None = None) -> Path:
        if output_path is None:
            output_path = self._working_dir / "reasoning_history.json"

        history_data = [
            {
                "goal": chain.goal,
                "conclusion": chain.conclusion,
                "overall_confidence": chain.overall_conffidence,
                "created_at": chain.created_at.isoformat(),
                "steps": [
                    {
                        "step_number": s.step_number,
                        "reasoning_type": s.reasoning_type.value,
                        "premise": s.premise,
                        "inference": s.inference,
                        "confidence": s.confidence,
                        "source": s.source,
                    }
                    for s in chain.steps
                ],
            }
            for chain in self._reasoning_history
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        logger.info("reasoning_history_exported", path=str(output_path))
        return output_path
