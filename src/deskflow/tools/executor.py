"""Parallel tool executor with dependency graph analysis.

Executes multiple tools in parallel when there are no dependencies
between them, improving overall task execution speed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from deskflow.errors import ToolExecutionError
from deskflow.observability.logging import get_logger
from deskflow.tools.registry import ToolRegistry

if __name__ == "__main__":
    from deskflow.core.models import ToolCall, ToolResult

logger = get_logger(__name__)


@dataclass
class ToolExecutionResult:
    """Result of executing a single tool call."""

    tool_name: str
    result: ToolResult | None
    error: Exception | None
    duration_ms: float = 0.0


@dataclass
class DependencyGraph:
    """Simple dependency graph for tool calls.

    Tools are nodes, dependencies are edges.
    """

    # Map from tool call ID to tool name
    calls: dict[str, str] = field(default_factory=dict)
    # Map from tool name to list of tool names it depends on
    dependencies: dict[str, list[str]] = field(default_factory=dict)

    def add_call(self, call_id: str, tool_name: str, depends_on: list[str] | None = None) -> None:
        """Add a tool call to the graph."""
        self.calls[call_id] = tool_name
        if depends_on:
            self.dependencies[tool_name] = depends_on
        elif tool_name not in self.dependencies:
            self.dependencies[tool_name] = []

    def get_execution_layers(self) -> list[list[str]]:
        """Get tool call IDs organized in execution layers.

        Tools in the same layer have no dependencies and can be executed in parallel.
        Uses topological sort to determine layers.

        Returns:
            List of lists of call IDs, where each inner list is a parallel execution layer.
        """
        # Build reverse dependency map (what does each tool depend on)
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {}

        # Initialize
        for tool_name in self.calls.values():
            in_degree[tool_name] = 0
            dependents[tool_name] = []

        # Count dependencies
        for tool_name, deps in self.dependencies.items():
            for dep in deps:
                if dep in self.calls.values():
                    in_degree[tool_name] = in_degree.get(tool_name, 0) + 1
                    dependents[dep].append(tool_name)

        # Kahn's algorithm for topological sort with layers
        layers: list[list[str]] = []
        current_layer: list[str] = []

        # Find all tools with no dependencies
        for tool_name, degree in in_degree.items():
            if degree == 0:
                current_layer.append(tool_name)

        while current_layer:
            # Get call IDs for tools in current layer
            layer_calls = [
                call_id for call_id, tool_name in self.calls.items()
                if tool_name in current_layer
            ]
            if layer_calls:
                layers.append(layer_calls)

            next_layer: list[str] = []
            for tool_name in current_layer:
                for dependent in dependents.get(tool_name, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_layer.append(dependent)

            current_layer = next_layer

        return layers


class ParallelToolExecutor:
    """Execute tools in parallel based on dependency analysis.

    Features:
    - Analyze tool call dependencies
    - Execute independent tools in parallel
    - Aggregate results in order
    - Support partial failure handling
    """

    def __init__(
        self,
        registry: ToolRegistry,
        max_parallel: int = 3,
        default_timeout: float = 30.0,
    ) -> None:
        self._registry = registry
        self._max_parallel = max_parallel
        self._default_timeout = default_timeout

    async def execute_all(
        self,
        tool_calls: list[ToolCall],
        timeout: float | None = None,
    ) -> list[ToolResult]:
        """Execute multiple tool calls with dependency-aware parallelism.

        Args:
            tool_calls: List of tool calls to execute.
            timeout: Optional timeout for each tool call.

        Returns:
            List of tool results in the same order as input calls.

        Raises:
            ToolExecutionError: If all tools fail.
        """
        if not tool_calls:
            return []

        # Build dependency graph
        graph = self._build_dependency_graph(tool_calls)

        # Get execution layers
        layers = graph.get_execution_layers()

        # Execute layer by layer
        results: dict[str, ToolExecutionResult] = {}

        for i, layer in enumerate(layers):
            logger.info(
                "executing_tool_layer",
                layer=i + 1,
                total_layers=len(layers),
                tools=len(layer),
            )

            # Execute layer in parallel (respecting max_parallel)
            layer_results = await self._execute_parallel(
                [call for call in tool_calls if call.id in layer],
                timeout=timeout,
            )

            # Store results
            for result in layer_results:
                results[result.tool_name] = result

        # Return results in original order
        ordered_results: list[ToolResult] = []
        for call in tool_calls:
            exec_result = results.get(call.name)
            if exec_result and exec_result.result:
                ordered_results.append(exec_result.result)
            elif exec_result and exec_result.error:
                # Create error result
                ordered_results.append(
                    ToolResult(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        success=False,
                        output="",
                        error=str(exec_result.error),
                        duration_ms=exec_result.duration_ms,
                    )
                )
            else:
                ordered_results.append(
                    ToolResult(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        success=False,
                        output="",
                        error="Tool execution result not found",
                        duration_ms=0.0,
                    )
                )

        return ordered_results

    def _build_dependency_graph(self, tool_calls: list[ToolCall]) -> DependencyGraph:
        """Build dependency graph from tool calls.

        Analyzes tool arguments to detect dependencies.
        For example, if tool B's argument references tool A's output,
        then B depends on A.

        Currently implements simple dependency detection:
        - Tools that operate on file paths may depend on previous file creation
        - Tools with explicit "depends_on" argument

        Args:
            tool_calls: List of tool calls.

        Returns:
            Dependency graph.
        """
        graph = DependencyGraph()

        # Track file operations for dependency detection
        file_creators: list[str] = []  # Tool names that create files
        file_writers: list[str] = []   # Tool names that write files

        for call in tool_calls:
            depends_on: list[str] = []

            # Check for explicit dependency
            if "depends_on" in call.arguments:
                depends_on = call.arguments["depends_on"]

            # Detect implicit dependencies
            # File read operations depend on file creation
            if call.name in ("file_read", "file_list"):
                path = call.arguments.get("path", "")
                # Check if any previous tool created this path
                for creator in file_creators:
                    depends_on.append(creator)

            # File write operations may depend on directory creation
            if call.name in ("file_write", "file_append"):
                path = call.arguments.get("path", "")
                # Directory should be created first
                for creator in file_creators:
                    if creator.startswith("file_"):
                        depends_on.append(creator)

            # Track file creators
            if call.name in ("file_write", "file_create", "dir_create"):
                file_creators.append(call.name)

            graph.add_call(call.id, call.name, depends_on if depends_on else None)

        return graph

    async def _execute_parallel(
        self,
        tool_calls: list[ToolCall],
        timeout: float | None = None,
    ) -> list[ToolExecutionResult]:
        """Execute tool calls in parallel with concurrency limit.

        Args:
            tool_calls: Tool calls to execute.
            timeout: Timeout for each call.

        Returns:
            List of execution results.
        """
        semaphore = asyncio.Semaphore(self._max_parallel)

        async def execute_with_semaphore(call: ToolCall) -> ToolExecutionResult:
            async with semaphore:
                return await self._execute_single(call, timeout)

        # Execute all calls in parallel (limited by semaphore)
        tasks = [execute_with_semaphore(call) for call in tool_calls]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed: list[ToolExecutionResult] = []
        for i, result in enumerate(results_raw):
            if isinstance(result, Exception):
                processed.append(
                    ToolExecutionResult(
                        tool_name=tool_calls[i].name,
                        result=None,
                        error=result,
                        duration_ms=0.0,
                    )
                )
            else:
                processed.append(result)

        return processed

    async def _execute_single(
        self,
        call: ToolCall,
        timeout: float | None = None,
    ) -> ToolExecutionResult:
        """Execute a single tool call.

        Args:
            call: Tool call to execute.
            timeout: Optional timeout.

        Returns:
            Execution result.
        """
        import time

        start = time.time()
        try:
            result = await self._registry.execute(
                call.name,
                call.arguments,
                timeout=timeout or self._default_timeout,
            )
            duration_ms = (time.time() - start) * 1000

            return ToolExecutionResult(
                tool_name=call.name,
                result=result,
                error=None,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            logger.warning(
                "tool_execution_error",
                tool_name=call.name,
                error=str(e),
            )

            return ToolExecutionResult(
                tool_name=call.name,
                result=None,
                error=e,
                duration_ms=duration_ms,
            )
