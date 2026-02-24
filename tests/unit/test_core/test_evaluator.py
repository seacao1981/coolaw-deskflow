"""Tests for task evaluation system."""

import pytest

from deskflow.core.evaluator import (
    TaskEvaluator,
    TaskEvaluation,
    EvaluationResult,
    EvaluationDimension,
    create_evaluator,
    evaluate_task,
    get_evaluator,
)


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_create_evaluation_result(self) -> None:
        """Test creating evaluation result."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=85.0,
        )

        assert result.dimension == EvaluationDimension.TASK_COMPLETION
        assert result.score == 85.0
        assert result.max_score == 100.0

    def test_percentage_calculation(self) -> None:
        """Test percentage calculation."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=85.0,
            max_score=100.0,
        )

        assert result.percentage == 85.0

    def test_grade_calculation_a(self) -> None:
        """Test grade A calculation."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=95.0,
        )
        assert result.grade == "A"

    def test_grade_calculation_b(self) -> None:
        """Test grade B calculation."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=85.0,
        )
        assert result.grade == "B"

    def test_grade_calculation_c(self) -> None:
        """Test grade C calculation."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=75.0,
        )
        assert result.grade == "C"

    def test_grade_calculation_d(self) -> None:
        """Test grade D calculation."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=65.0,
        )
        assert result.grade == "D"

    def test_grade_calculation_f(self) -> None:
        """Test grade F calculation."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=50.0,
        )
        assert result.grade == "F"

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=85.0,
            details={"key": "value"},
            suggestions=["suggestion 1"],
        )

        data = result.to_dict()

        assert data["dimension"] == "task_completion"
        assert data["score"] == 85.0
        assert data["percentage"] == 85.0
        assert data["grade"] == "B"
        assert data["details"] == {"key": "value"}
        assert data["suggestions"] == ["suggestion 1"]


class TestTaskEvaluation:
    """Tests for TaskEvaluation dataclass."""

    def test_create_task_evaluation(self) -> None:
        """Test creating task evaluation."""
        evaluation = TaskEvaluation(
            task_id="task-001",
            task_description="Test task",
        )

        assert evaluation.task_id == "task-001"
        assert evaluation.task_description == "Test task"
        assert evaluation.overall_score == 0.0
        assert len(evaluation.results) == 0

    def test_add_result(self) -> None:
        """Test adding evaluation result."""
        evaluation = TaskEvaluation(
            task_id="task-001",
            task_description="Test task",
        )

        result = EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=80.0,
        )
        evaluation.add_result(result)

        assert len(evaluation.results) == 1
        assert evaluation.overall_score == 80.0

    def test_overall_percentage(self) -> None:
        """Test overall percentage calculation."""
        evaluation = TaskEvaluation(
            task_id="task-001",
            task_description="Test task",
        )

        evaluation.add_result(EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=80.0,
        ))
        evaluation.add_result(EvaluationResult(
            dimension=EvaluationDimension.RESPONSE_QUALITY,
            score=90.0,
        ))

        assert evaluation.overall_percentage == 85.0

    def test_overall_grade(self) -> None:
        """Test overall grade calculation."""
        evaluation = TaskEvaluation(
            task_id="task-001",
            task_description="Test task",
        )

        evaluation.add_result(EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=95.0,
        ))

        assert evaluation.overall_grade == "A"

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        evaluation = TaskEvaluation(
            task_id="task-001",
            task_description="Test task",
        )

        evaluation.add_result(EvaluationResult(
            dimension=EvaluationDimension.TASK_COMPLETION,
            score=85.0,
        ))

        data = evaluation.to_dict()

        assert data["task_id"] == "task-001"
        assert data["overall_score"] == 85.0
        assert data["overall_grade"] == "B"
        assert len(data["results"]) == 1


class TestTaskEvaluator:
    """Tests for TaskEvaluator class."""

    @pytest.fixture
    def evaluator(self) -> TaskEvaluator:
        """Create evaluator for testing."""
        return TaskEvaluator()

    def test_create_evaluator(self) -> None:
        """Test creating evaluator."""
        evaluator = TaskEvaluator()
        assert evaluator is not None

    def test_evaluate_task_completion_success(self, evaluator: TaskEvaluator) -> None:
        """Test successful task completion evaluation."""
        result = evaluator.evaluate_task_completion(
            task_description="Write a function",
            task_result="Here is the function: def hello(): pass",
            requirements=["function", "hello"],
        )

        assert result.dimension == EvaluationDimension.TASK_COMPLETION
        assert result.score > 50

    def test_evaluate_task_completion_empty(self, evaluator: TaskEvaluator) -> None:
        """Test empty task completion evaluation."""
        result = evaluator.evaluate_task_completion(
            task_description="Write a function",
            task_result="",
        )

        assert result.score == 0.0
        assert len(result.suggestions) > 0

    def test_evaluate_task_completion_missing_requirements(
        self, evaluator: TaskEvaluator
    ) -> None:
        """Test task completion with missing requirements."""
        result = evaluator.evaluate_task_completion(
            task_description="Write a function",
            task_result="def hello(): pass",
            requirements=["function", "async", "test"],
        )

        assert result.score < 100
        assert "async" in result.details.get("requirements_missing", [])

    def test_evaluate_token_efficiency_optimal(self, evaluator: TaskEvaluator) -> None:
        """Test optimal token efficiency."""
        result = evaluator.evaluate_token_efficiency(
            tokens_used=3000,
            tokens_expected=4000,
        )

        assert result.score == 100
        assert result.dimension == EvaluationDimension.TOKEN_EFFICIENCY

    def test_evaluate_token_efficiency_over_budget(
        self, evaluator: TaskEvaluator
    ) -> None:
        """Test token efficiency over budget."""
        result = evaluator.evaluate_token_efficiency(
            tokens_used=8000,
            tokens_expected=4000,
        )

        assert result.score < 80
        assert len(result.suggestions) > 0

    def test_evaluate_token_efficiency_under_budget(
        self, evaluator: TaskEvaluator
    ) -> None:
        """Test token efficiency under budget."""
        result = evaluator.evaluate_token_efficiency(
            tokens_used=1000,
            tokens_expected=4000,
        )

        assert result.score < 100  # Penalized for being too brief
        assert "more detailed" in result.suggestions[0].lower()

    def test_evaluate_response_quality_good(self, evaluator: TaskEvaluator) -> None:
        """Test good response quality evaluation."""
        result = evaluator.evaluate_response_quality(
            response="""
# Solution

Here's a comprehensive answer to your question:

## Key Points
1. First point
2. Second point
3. Third point

```python
def example():
    pass
```
""",
            context="Explain the concept",
        )

        assert result.score > 70
        assert result.details.get("has_structure") is True
        assert result.details.get("has_code") is True

    def test_evaluate_response_quality_poor(self, evaluator: TaskEvaluator) -> None:
        """Test poor response quality evaluation."""
        result = evaluator.evaluate_response_quality(
            response="ok",
            context="Explain quantum physics",
        )

        assert result.score < 70  # Poor quality but has base score
        assert len(result.suggestions) > 0

    def test_evaluate_code_quality_good(self, evaluator: TaskEvaluator) -> None:
        """Test good code quality evaluation."""
        result = evaluator.evaluate_code_quality(
            code="""
def calculate_sum(numbers: list) -> int:
    '''Calculate sum of numbers.'''
    try:
        return sum(numbers)
    except TypeError as e:
        raise ValueError("Invalid input") from e
""",
            language="python",
        )

        assert result.score > 70
        assert result.details.get("has_docstrings") is True
        assert result.details.get("has_error_handling") is True

    def test_evaluate_code_quality_poor(self, evaluator: TaskEvaluator) -> None:
        """Test poor code quality evaluation."""
        result = evaluator.evaluate_code_quality(
            code="def f(n):return n+1",
            language="python",
        )

        assert result.score < 80  # Poor quality code
        assert len(result.suggestions) > 0

    def test_evaluate_safety_clean(self, evaluator: TaskEvaluator) -> None:
        """Test safety evaluation with clean content."""
        result = evaluator.evaluate_safety(
            content="This is safe content without secrets",
        )

        assert result.score == 100
        assert len(result.details.get("issues_found", [])) == 0

    def test_evaluate_safety_issues(self, evaluator: TaskEvaluator) -> None:
        """Test safety evaluation with issues."""
        result = evaluator.evaluate_safety(
            content="api_key = sk-12345password",
        )

        assert result.score < 100
        assert len(result.details.get("issues_found", [])) > 0

    def test_comprehensive_evaluate(self, evaluator: TaskEvaluator) -> None:
        """Test comprehensive evaluation."""
        result = evaluator.comprehensive_evaluate(
            task_id="task-001",
            task_description="Write a hello world function",
            task_result="""
# Hello World Function

Here's the implementation:

```python
def hello_world():
    '''Print hello world.'''
    print("Hello, World!")
```
""",
            code="def hello_world(): pass",
            tokens_used=500,
        )

        assert result.overall_score > 0
        assert len(result.results) >= 4  # At least 4 dimensions
        assert result.summary != ""

    def test_get_evaluation_history(self, evaluator: TaskEvaluator) -> None:
        """Test getting evaluation history."""
        evaluator.comprehensive_evaluate(
            task_id="task-001",
            task_description="Test task",
            task_result="Result",
        )

        history = evaluator.get_evaluation_history()

        assert len(history) == 1

    def test_get_average_scores(self, evaluator: TaskEvaluator) -> None:
        """Test getting average scores."""
        evaluator.comprehensive_evaluate(
            task_id="task-001",
            task_description="Test task",
            task_result="Good result with quality content",
        )

        averages = evaluator.get_average_scores()

        assert len(averages) > 0
        assert all(isinstance(v, float) for v in averages.values())


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_evaluator(self) -> None:
        """Test create_evaluator function."""
        evaluator = create_evaluator()
        assert isinstance(evaluator, TaskEvaluator)

    def test_evaluate_task(self) -> None:
        """Test evaluate_task function."""
        result = evaluate_task(
            task_id="task-001",
            task_description="Test task",
            task_result="Test result",
        )

        assert isinstance(result, TaskEvaluation)
        assert result.task_id == "task-001"

    def test_get_evaluator_singleton(self) -> None:
        """Test get_evaluator singleton."""
        evaluator1 = get_evaluator()
        evaluator2 = get_evaluator()

        assert evaluator1 is evaluator2


class TestEvaluationDimensions:
    """Tests for evaluation dimensions."""

    def test_evaluation_dimension_values(self) -> None:
        """Test evaluation dimension enum values."""
        assert EvaluationDimension.TASK_COMPLETION.value == "task_completion"
        assert EvaluationDimension.TOKEN_EFFICIENCY.value == "token_efficiency"
        assert EvaluationDimension.RESPONSE_QUALITY.value == "response_quality"
        assert EvaluationDimension.CODE_QUALITY.value == "code_quality"
        assert EvaluationDimension.SAFETY.value == "safety"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def evaluator(self) -> TaskEvaluator:
        return TaskEvaluator()

    def test_empty_task_result(self, evaluator: TaskEvaluator) -> None:
        """Test evaluation with empty task result."""
        result = evaluator.evaluate_task_completion(
            task_description="Do something",
            task_result="",
        )

        assert result.score == 0.0

    def test_very_long_response(self, evaluator: TaskEvaluator) -> None:
        """Test evaluation with very long response."""
        long_response = "word " * 10000

        result = evaluator.evaluate_response_quality(
            response=long_response,
            context="Test",
        )

        assert result.score < 100  # Penalized for length
        assert any("long" in s.lower() for s in result.suggestions)

    def test_code_without_documentation(
        self, evaluator: TaskEvaluator
    ) -> None:
        """Test code evaluation without documentation."""
        result = evaluator.evaluate_code_quality(
            code="def f():\n    return 42",
        )

        assert result.score < 80  # Lower score without docs
        assert any("doc" in s.lower() for s in result.suggestions)

    def test_token_efficiency_zero_expected(
        self, evaluator: TaskEvaluator
    ) -> None:
        """Test token efficiency with zero expected tokens."""
        result = evaluator.evaluate_token_efficiency(
            tokens_used=100,
            tokens_expected=0,
        )

        assert result.score == 50  # Can't evaluate
