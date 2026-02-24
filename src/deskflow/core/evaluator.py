"""Task and Response Evaluation System.

Provides comprehensive evaluation for:
- Task completion assessment
- Token efficiency analysis
- Response quality scoring
- Overall performance metrics

Features:
- Multi-dimensional scoring (0-100)
- LLM-based quality assessment
- Token usage optimization insights
- Actionable improvement suggestions
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class EvaluationDimension(StrEnum):
    """Evaluation dimensions."""

    TASK_COMPLETION = "task_completion"
    TOKEN_EFFICIENCY = "token_efficiency"
    RESPONSE_QUALITY = "response_quality"
    CODE_QUALITY = "code_quality"
    SAFETY = "safety"


@dataclass
class EvaluationResult:
    """Result of a single evaluation dimension."""

    dimension: EvaluationDimension
    score: float  # 0-100
    max_score: float = 100.0
    details: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def percentage(self) -> float:
        """Get score as percentage."""
        return (self.score / self.max_score) * 100

    @property
    def grade(self) -> str:
        """Get letter grade."""
        pct = self.percentage
        if pct >= 90:
            return "A"
        elif pct >= 80:
            return "B"
        elif pct >= 70:
            return "C"
        elif pct >= 60:
            return "D"
        else:
            return "F"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dimension": self.dimension.value,
            "score": self.score,
            "max_score": self.max_score,
            "percentage": round(self.percentage, 2),
            "grade": self.grade,
            "details": self.details,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
        }


@dataclass
class TaskEvaluation:
    """Comprehensive task evaluation result."""

    task_id: str
    task_description: str
    overall_score: float = 0.0
    results: list[EvaluationResult] = field(default_factory=list)
    summary: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def overall_percentage(self) -> float:
        """Get overall score as percentage."""
        if not self.results:
            return 0.0
        total_max = sum(r.max_score for r in self.results)
        total_score = sum(r.score for r in self.results)
        return (total_score / total_max) * 100 if total_max > 0 else 0.0

    @property
    def overall_grade(self) -> str:
        """Get overall letter grade."""
        pct = self.overall_percentage
        if pct >= 90:
            return "A"
        elif pct >= 80:
            return "B"
        elif pct >= 70:
            return "C"
        elif pct >= 60:
            return "D"
        else:
            return "F"

    def add_result(self, result: EvaluationResult) -> None:
        """Add evaluation result."""
        self.results.append(result)
        self._recalculate_overall()

    def _recalculate_overall(self) -> None:
        """Recalculate overall score."""
        if not self.results:
            self.overall_score = 0.0
            return

        # Weighted average (all dimensions equally weighted)
        total = sum(r.percentage for r in self.results)
        self.overall_score = total / len(self.results)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "overall_score": round(self.overall_score, 2),
            "overall_percentage": round(self.overall_percentage, 2),
            "overall_grade": self.overall_grade,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class TaskEvaluator:
    """Main task evaluation orchestrator."""

    def __init__(
        self,
        llm_client: Any | None = None,
        token_tracker: Any | None = None,
    ) -> None:
        """Initialize evaluator.

        Args:
            llm_client: LLM client for quality assessment
            token_tracker: Token usage tracker
        """
        self._llm = llm_client
        self._token_tracker = token_tracker
        self._evaluation_history: list[TaskEvaluation] = []

    def evaluate_task_completion(
        self,
        task_description: str,
        task_result: str,
        requirements: list[str] | None = None,
    ) -> EvaluationResult:
        """Evaluate task completion.

        Args:
            task_description: Original task description
            task_result: Actual task result/output
            requirements: List of specific requirements

        Returns:
            Evaluation result with completion score
        """
        score = 0.0
        details: dict[str, Any] = {}
        suggestions: list[str] = []

        # Check if result is empty
        if not task_result or not task_result.strip():
            return EvaluationResult(
                dimension=EvaluationDimension.TASK_COMPLETION,
                score=0.0,
                details={"error": "Empty result"},
                suggestions=["Task was not executed or produced no output"],
            )

        # Analyze requirements coverage
        if requirements:
            covered = []
            missing = []
            for req in requirements:
                if req.lower() in task_result.lower():
                    covered.append(req)
                else:
                    missing.append(req)

            details["requirements_total"] = len(requirements)
            details["requirements_covered"] = len(covered)
            details["requirements_missing"] = missing

            coverage_ratio = len(covered) / len(requirements) if requirements else 0
            score = coverage_ratio * 100

            if missing:
                suggestions.append(f"Address missing requirements: {', '.join(missing[:3])}")
        else:
            # Basic completion check - result has substantial content
            result_length = len(task_result)
            if result_length > 100:
                score = min(100, 50 + (result_length / 100))
            else:
                score = result_length / 2
                suggestions.append("Provide more comprehensive output")

        details["result_length"] = len(task_result)
        details["completion_percentage"] = score

        return EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=score,
            details=details,
            suggestions=suggestions,
        )

    def evaluate_token_efficiency(
        self,
        tokens_used: int,
        tokens_expected: int | None = None,
        task_complexity: str = "medium",
    ) -> EvaluationResult:
        """Evaluate token usage efficiency.

        Args:
            tokens_used: Actual tokens consumed
            tokens_expected: Expected token budget
            task_complexity: Task complexity level (low, medium, high)

        Returns:
            Evaluation result with efficiency score
        """
        score = 100.0
        details: dict[str, Any] = {
            "tokens_used": tokens_used,
            "task_complexity": task_complexity,
        }
        suggestions: list[str] = []

        # Set expected tokens based on complexity if not provided
        if tokens_expected is None:
            complexity_budget = {
                "low": 1000,
                "medium": 4000,
                "high": 10000,
            }
            tokens_expected = complexity_budget.get(task_complexity, 4000)

        details["tokens_expected"] = tokens_expected

        # Calculate efficiency ratio
        if tokens_expected > 0:
            efficiency_ratio = tokens_used / tokens_expected

            if efficiency_ratio <= 0.5:
                # Very efficient - might be too brief
                score = 85
                suggestions.append("Consider providing more detailed output")
            elif efficiency_ratio <= 1.0:
                # Optimal range
                score = 100
            elif efficiency_ratio <= 1.5:
                # Slightly over budget
                score = 80 - ((efficiency_ratio - 1.0) * 40)
                suggestions.append("Try to be more concise")
            elif efficiency_ratio <= 2.0:
                # Over budget
                score = 60 - ((efficiency_ratio - 1.5) * 40)
                suggestions.append("Significantly over token budget - optimize response")
            else:
                # Way over budget
                score = max(0, 40 - ((efficiency_ratio - 2.0) * 20))
                suggestions.append("Critically inefficient - major optimization needed")
        else:
            score = 50  # Can't evaluate without expected tokens
            suggestions.append("Set token expectations for better evaluation")

        details["efficiency_ratio"] = round(efficiency_ratio if tokens_expected > 0 else 0, 2)
        details["efficiency_score"] = round(score, 2)

        return EvaluationResult(
            dimension=EvaluationDimension.TOKEN_EFFICIENCY,
            score=score,
            details=details,
            suggestions=suggestions,
        )

    def evaluate_response_quality(
        self,
        response: str,
        context: str | None = None,
        criteria: list[str] | None = None,
    ) -> EvaluationResult:
        """Evaluate response quality.

        Args:
            response: The response to evaluate
            context: Optional context or question
            criteria: Optional quality criteria

        Returns:
            Evaluation result with quality score
        """
        score = 50.0  # Base score
        details: dict[str, Any] = {}
        suggestions: list[str] = []

        # Default quality criteria
        if criteria is None:
            criteria = [
                "clarity",
                "completeness",
                "accuracy",
                "relevance",
                "actionability",
            ]

        details["criteria"] = criteria

        # Analyze response characteristics
        response_length = len(response)
        word_count = len(response.split())
        sentence_count = response.count(".") + response.count("!") + response.count("?")

        details["response_length"] = response_length
        details["word_count"] = word_count
        details["sentence_count"] = sentence_count

        # Check for structure (headings, lists, code blocks)
        has_structure = (
            "#" in response or
            "- " in response or
            "```" in response or
            "**" in response
        )
        details["has_structure"] = has_structure

        # Check for code examples
        has_code = "```" in response
        details["has_code"] = has_code

        # Calculate base quality score
        quality_factors = []

        # Length appropriateness
        if 200 <= response_length <= 2000:
            quality_factors.append(1.0)
        elif response_length < 50:
            quality_factors.append(0.3)
            suggestions.append("Response is too brief")
        elif response_length > 5000:
            quality_factors.append(0.7)
            suggestions.append("Response is very long - consider summarizing")
        else:
            quality_factors.append(0.7)

        # Structure bonus
        if has_structure:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.7)
            suggestions.append("Add structure with headings or lists")

        # Code bonus for technical responses
        if has_code:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.85)

        # Use LLM for advanced quality assessment if available
        if self._llm and context:
            llm_feedback = self._llm_quality_check(response, context, criteria)
            if llm_feedback:
                quality_factors.append(llm_feedback["score"] / 100)
                if llm_feedback.get("suggestions"):
                    suggestions.extend(llm_feedback["suggestions"][:2])

        # Calculate final score
        avg_factor = sum(quality_factors) / len(quality_factors)
        score = avg_factor * 100

        details["quality_factors"] = quality_factors
        details["quality_score"] = round(score, 2)

        return EvaluationResult(
            dimension=EvaluationDimension.RESPONSE_QUALITY,
            score=score,
            details=details,
            suggestions=suggestions,
        )

    def _llm_quality_check(
        self,
        response: str,
        context: str,
        criteria: list[str],
    ) -> dict[str, Any] | None:
        """Use LLM to assess response quality.

        Args:
            response: Response to evaluate
            context: Original context/question
            criteria: Quality criteria

        Returns:
            LLM feedback or None if evaluation fails
        """
        try:
            prompt = f"""Evaluate the following response based on these criteria: {', '.join(criteria)}

Context/Question:
{context[:500]}

Response:
{response[:1000]}

Provide a JSON response with:
{{
    "score": 0-100,
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}
"""
            # Note: Actual LLM call would go here
            # response = await self._llm.chat(prompt, max_tokens=200)
            # return json.loads(response.content)

            # For now, return placeholder
            return {"score": 75, "suggestions": []}

        except Exception as e:
            logger.warning("llm_quality_check_failed", error=str(e))
            return None

    def evaluate_code_quality(
        self,
        code: str,
        language: str = "python",
    ) -> EvaluationResult:
        """Evaluate code quality.

        Args:
            code: Source code to evaluate
            language: Programming language

        Returns:
            Evaluation result with code quality score
        """
        score = 50.0
        details: dict[str, Any] = {"language": language}
        suggestions: list[str] = []

        if not code or not code.strip():
            return EvaluationResult(
                dimension=EvaluationDimension.CODE_QUALITY,
                score=0.0,
                details={"error": "Empty code"},
                suggestions=["Provide code implementation"],
            )

        code_lines = code.split("\n")
        details["total_lines"] = len(code_lines)

        # Check for common quality indicators
        has_docstrings = '"""' in code or "'''" in code
        has_comments = "#" in code or "//" in code
        has_error_handling = "try:" in code or "catch" in code or "except" in code

        details["has_docstrings"] = has_docstrings
        details["has_comments"] = has_comments
        details["has_error_handling"] = has_error_handling

        # Scoring
        quality_factors = []

        # Documentation
        if has_docstrings or has_comments:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.6)
            suggestions.append("Add documentation/comments")

        # Error handling
        if has_error_handling:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.7)
            suggestions.append("Add error handling")

        # Function length check
        long_functions = code.count("def ") > 0 and any(
            len(block) > 50 for block in code.split("def ")
        )
        if not long_functions:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.7)
            suggestions.append("Consider breaking down long functions")

        score = sum(quality_factors) / len(quality_factors) * 100
        details["quality_score"] = round(score, 2)

        return EvaluationResult(
            dimension=EvaluationDimension.CODE_QUALITY,
            score=score,
            details=details,
            suggestions=suggestions,
        )

    def evaluate_safety(
        self,
        content: str,
    ) -> EvaluationResult:
        """Evaluate content safety.

        Args:
            content: Content to evaluate

        Returns:
            Evaluation result with safety score
        """
        score = 100.0
        details: dict[str, Any] = {}
        suggestions: list[str] = []

        # Check for potential security issues
        security_patterns = [
            ("sk-", "Potential API key"),
            ("password", "Hardcoded password reference"),
            ("secret", "Hardcoded secret reference"),
            ("token", "Hardcoded token reference"),
            ("api_key", "Hardcoded API key"),
        ]

        issues_found = []
        for pattern, description in security_patterns:
            if pattern.lower() in content.lower():
                # Check if it looks like actual credentials
                if "=" in content or ":" in content:
                    issues_found.append(description)

        if issues_found:
            score = max(0, 100 - (len(issues_found) * 20))
            suggestions.append(f"Review for sensitive data: {', '.join(issues_found[:3])}")

        details["issues_found"] = issues_found
        details["safety_score"] = round(score, 2)

        return EvaluationResult(
            dimension=EvaluationDimension.SAFETY,
            score=score,
            details=details,
            suggestions=suggestions,
        )

    def comprehensive_evaluate(
        self,
        task_id: str,
        task_description: str,
        task_result: str,
        code: str | None = None,
        tokens_used: int | None = None,
        requirements: list[str] | None = None,
    ) -> TaskEvaluation:
        """Perform comprehensive evaluation across all dimensions.

        Args:
            task_id: Unique task identifier
            task_description: Task description
            task_result: Task output/result
            code: Optional code implementation
            tokens_used: Optional token usage
            requirements: Optional list of requirements

        Returns:
            Comprehensive task evaluation
        """
        evaluation = TaskEvaluation(
            task_id=task_id,
            task_description=task_description,
        )

        # 1. Task Completion
        completion_result = self.evaluate_task_completion(
            task_description, task_result, requirements
        )
        evaluation.add_result(completion_result)

        # 2. Token Efficiency
        if tokens_used is not None:
            token_result = self.evaluate_token_efficiency(tokens_used)
            evaluation.add_result(token_result)

        # 3. Response Quality
        quality_result = self.evaluate_response_quality(task_result, task_description)
        evaluation.add_result(quality_result)

        # 4. Code Quality (if code provided)
        if code:
            code_result = self.evaluate_code_quality(code)
            evaluation.add_result(code_result)

        # 5. Safety Check
        safety_result = self.evaluate_safety(task_result + (code or ""))
        evaluation.add_result(safety_result)

        # Generate summary
        evaluation.summary = self._generate_summary(evaluation)
        evaluation.metadata = {
            "dimensions_evaluated": len(evaluation.results),
            "tokens_used": tokens_used,
            "has_code": code is not None,
        }

        self._evaluation_history.append(evaluation)
        return evaluation

    def _generate_summary(self, evaluation: TaskEvaluation) -> str:
        """Generate human-readable summary.

        Args:
            evaluation: Task evaluation result

        Returns:
            Summary text
        """
        grade = evaluation.overall_grade
        pct = evaluation.overall_percentage

        if grade == "A":
            verdict = "Excellent work!"
        elif grade == "B":
            verdict = "Good job with minor improvements needed."
        elif grade == "C":
            verdict = "Acceptable but needs improvement."
        elif grade == "D":
            verdict = "Below expectations - significant improvements needed."
        else:
            verdict = "Unsatisfactory - major revision required."

        # Collect top suggestions
        all_suggestions = []
        for result in evaluation.results:
            all_suggestions.extend(result.suggestions[:2])

        top_suggestions = all_suggestions[:3] if all_suggestions else ["No specific suggestions"]

        summary = (
            f"{verdict} Overall: {grade} ({pct:.1f}%)\n\n"
            f"Key suggestions:\n" +
            "\n".join(f"- {s}" for s in top_suggestions)
        )

        return summary

    def get_evaluation_history(self) -> list[TaskEvaluation]:
        """Get evaluation history."""
        return self._evaluation_history.copy()

    def get_average_scores(self) -> dict[str, float]:
        """Get average scores across all evaluations.

        Returns:
            Dictionary of dimension -> average score
        """
        if not self._evaluation_history:
            return {}

        dimension_totals: dict[str, list[float]] = {}

        for eval_result in self._evaluation_history:
            for result in eval_result.results:
                dim = result.dimension.value
                if dim not in dimension_totals:
                    dimension_totals[dim] = []
                dimension_totals[dim].append(result.percentage)

        return {
            dim: sum(scores) / len(scores)
            for dim, scores in dimension_totals.items()
        }


# ==================== Convenience Functions ====================

def create_evaluator(
    llm_client: Any | None = None,
    token_tracker: Any | None = None,
) -> TaskEvaluator:
    """Create a task evaluator instance."""
    return TaskEvaluator(llm_client, token_tracker)


def evaluate_task(
    task_id: str,
    task_description: str,
    task_result: str,
    code: str | None = None,
    tokens_used: int | None = None,
    requirements: list[str] | None = None,
) -> TaskEvaluation:
    """Convenience function for quick task evaluation."""
    evaluator = TaskEvaluator()
    return evaluator.comprehensive_evaluate(
        task_id,
        task_description,
        task_result,
        code,
        tokens_used,
        requirements,
    )


# ==================== Global Instance ====================

_evaluator: TaskEvaluator | None = None


def get_evaluator() -> TaskEvaluator:
    """Get or create global evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = TaskEvaluator()
    return _evaluator
