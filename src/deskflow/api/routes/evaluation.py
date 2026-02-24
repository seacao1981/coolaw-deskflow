"""Evaluation system API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Any

from deskflow.observability.logging import get_logger
from deskflow.core.evaluator import (
    TaskEvaluator,
    TaskEvaluation,
    EvaluationDimension,
    get_evaluator,
    evaluate_task,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


# ==================== Request/Response Models ====================

class TaskEvaluationRequest(BaseModel):
    """Request model for task evaluation."""

    task_id: str = Field(..., description="Unique task identifier")
    task_description: str = Field(..., description="Task description")
    task_result: str = Field(..., description="Task output/result")
    code: str | None = Field(None, description="Optional code implementation")
    tokens_used: int | None = Field(None, description="Optional token usage")
    requirements: list[str] | None = Field(None, description="Optional requirements list")


class TaskEvaluationResponse(BaseModel):
    """Response model for task evaluation."""

    task_id: str
    task_description: str
    overall_score: float
    overall_percentage: float
    overall_grade: str
    results: list[dict[str, Any]]
    summary: str
    metadata: dict[str, Any]

    @classmethod
    def from_evaluation(cls, evaluation: TaskEvaluation) -> "TaskEvaluationResponse":
        """Create response from evaluation result."""
        return cls(
            task_id=evaluation.task_id,
            task_description=evaluation.task_description,
            overall_score=evaluation.overall_score,
            overall_percentage=evaluation.overall_percentage,
            overall_grade=evaluation.overall_grade,
            results=evaluation.to_dict()["results"],
            summary=evaluation.summary,
            metadata=evaluation.metadata,
        )


class QuickEvaluationRequest(BaseModel):
    """Request model for quick single-dimension evaluation."""

    content: str = Field(..., description="Content to evaluate")
    dimension: str = Field(..., description="Evaluation dimension")
    context: str | None = Field(None, description="Optional context")


class QuickEvaluationResponse(BaseModel):
    """Response model for quick evaluation."""

    dimension: str
    score: float
    percentage: float
    grade: str
    suggestions: list[str]
    details: dict[str, Any]


class EvaluationHistoryResponse(BaseModel):
    """Response model for evaluation history."""

    total_evaluations: int
    average_scores: dict[str, float]
    recent_evaluations: list[dict[str, Any]]


# ==================== Routes ====================

@router.post("/task", response_model=TaskEvaluationResponse)
async def evaluate_task_endpoint(request: TaskEvaluationRequest):
    """Evaluate a completed task.

    Performs comprehensive evaluation across multiple dimensions:
    - Task completion
    - Token efficiency
    - Response quality
    - Code quality (if code provided)
    - Safety check

    Args:
        request: Evaluation request with task details

    Returns:
        Comprehensive evaluation result
    """
    try:
        evaluation = evaluate_task(
            task_id=request.task_id,
            task_description=request.task_description,
            task_result=request.task_result,
            code=request.code,
            tokens_used=request.tokens_used,
            requirements=request.requirements,
        )

        return TaskEvaluationResponse.from_evaluation(evaluation)

    except Exception as e:
        logger.error("task_evaluation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/quick", response_model=QuickEvaluationResponse)
async def quick_evaluate(request: QuickEvaluationRequest):
    """Quick single-dimension evaluation.

    Args:
        request: Quick evaluation request

    Returns:
        Single dimension evaluation result
    """
    evaluator = get_evaluator()

    try:
        dimension = EvaluationDimension(request.dimension)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension. Valid options: {[d.value for d in EvaluationDimension]}"
        )

    if dimension == EvaluationDimension.TASK_COMPLETION:
        result = evaluator.evaluate_task_completion(
            task_description=request.context or "Task",
            task_result=request.content,
        )
    elif dimension == EvaluationDimension.RESPONSE_QUALITY:
        result = evaluator.evaluate_response_quality(
            response=request.content,
            context=request.context,
        )
    elif dimension == EvaluationDimension.CODE_QUALITY:
        result = evaluator.evaluate_code_quality(
            code=request.content,
        )
    elif dimension == EvaluationDimension.SAFETY:
        result = evaluator.evaluate_safety(
            content=request.content,
        )
    elif dimension == EvaluationDimension.TOKEN_EFFICIENCY:
        # For token efficiency, content should be token count
        try:
            tokens = int(request.content)
            result = evaluator.evaluate_token_efficiency(tokens_used=tokens)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Token efficiency evaluation requires numeric token count"
            )
    else:
        raise HTTPException(status_code=400, detail="Unsupported dimension")

    return QuickEvaluationResponse(
        dimension=result.dimension.value,
        score=result.score,
        percentage=result.percentage,
        grade=result.grade,
        suggestions=result.suggestions,
        details=result.details,
    )


@router.get("/history", response_model=EvaluationHistoryResponse)
async def get_evaluation_history(limit: int = 10):
    """Get evaluation history.

    Args:
        limit: Maximum number of recent evaluations to return

    Returns:
        Evaluation history with statistics
    """
    evaluator = get_evaluator()
    history = evaluator.get_evaluation_history()
    averages = evaluator.get_average_scores()

    recent = history[-limit:] if history else []

    return EvaluationHistoryResponse(
        total_evaluations=len(history),
        average_scores=averages,
        recent_evaluations=[e.to_dict() for e in recent],
    )


@router.get("/dimensions")
async def list_evaluation_dimensions():
    """List available evaluation dimensions.

    Returns:
        List of evaluation dimensions with descriptions
    """
    dimensions = {
        EvaluationDimension.TASK_COMPLETION.value: {
            "description": "Evaluates how well the task was completed",
            "criteria": ["Requirements coverage", "Output completeness"],
        },
        EvaluationDimension.TOKEN_EFFICIENCY.value: {
            "description": "Evaluates token usage efficiency",
            "criteria": ["Budget adherence", "Conciseness"],
        },
        EvaluationDimension.RESPONSE_QUALITY.value: {
            "description": "Evaluates overall response quality",
            "criteria": ["Clarity", "Completeness", "Relevance", "Structure"],
        },
        EvaluationDimension.CODE_QUALITY.value: {
            "description": "Evaluates code implementation quality",
            "criteria": ["Documentation", "Error handling", "Function length"],
        },
        EvaluationDimension.SAFETY.value: {
            "description": "Checks for security and safety issues",
            "criteria": ["Sensitive data", "Security patterns"],
        },
    }

    return {"dimensions": dimensions}


@router.post("/batch", response_model=list[TaskEvaluationResponse])
async def batch_evaluate(
    requests: list[TaskEvaluationRequest] = Body(
        ...,
        description="List of evaluation requests",
    ),
):
    """Batch evaluate multiple tasks.

    Args:
        requests: List of evaluation requests

    Returns:
        List of evaluation results
    """
    results = []

    for request in requests:
        try:
            evaluation = evaluate_task(
                task_id=request.task_id,
                task_description=request.task_description,
                task_result=request.task_result,
                code=request.code,
                tokens_used=request.tokens_used,
                requirements=request.requirements,
            )
            results.append(TaskEvaluationResponse.from_evaluation(evaluation))
        except Exception as e:
            logger.error("batch_evaluation_item_failed", task_id=request.task_id, error=str(e))
            # Continue with other evaluations
            results.append(TaskEvaluationResponse(
                task_id=request.task_id,
                task_description=request.task_description,
                overall_score=0,
                overall_percentage=0,
                overall_grade="F",
                results=[],
                summary=f"Evaluation failed: {str(e)}",
                metadata={"error": str(e)},
            ))

    return results


# ==================== Health Check ====================

@router.get("/health")
async def evaluation_health():
    """Check evaluation system health.

    Returns:
        Health status
    """
    try:
        evaluator = get_evaluator()
        history = evaluator.get_evaluation_history()

        return {
            "status": "healthy",
            "evaluations_performed": len(history),
            "system": "evaluation",
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "system": "evaluation",
        }
