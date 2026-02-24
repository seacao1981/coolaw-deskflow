"""Ralph Loop - the "never give up" retry mechanism.

Named after the concept of persistent task completion: if a task fails,
the agent analyzes the failure and tries again with a new strategy.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = get_logger(__name__)


class RalphLoop:
    """Persistent task execution loop with intelligent retry.

    Executes a coroutine repeatedly until it succeeds or max retries is reached.
    Supports cancellation via an external event.
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
    ) -> None:
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._backoff_factor = backoff_factor
        self._max_delay = max_delay
        self._cancel_event = asyncio.Event()
        self._is_running = False
        self._current_attempt = 0

    @property
    def is_running(self) -> bool:
        """Whether the loop is currently executing."""
        return self._is_running

    @property
    def current_attempt(self) -> int:
        """Current retry attempt number (0-based)."""
        return self._current_attempt

    def cancel(self) -> None:
        """Request cancellation of the current loop."""
        self._cancel_event.set()
        logger.info("ralph_loop_cancel_requested")

    def reset(self) -> None:
        """Reset the loop for reuse."""
        self._cancel_event.clear()
        self._is_running = False
        self._current_attempt = 0

    async def execute(
        self,
        task: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        on_retry: Callable[[int, Exception], Coroutine[Any, Any, None]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a task with retry logic.

        Args:
            task: Async callable to execute.
            *args: Positional arguments for the task.
            on_retry: Optional callback called before each retry with
                (attempt_number, last_exception).
            **kwargs: Keyword arguments for the task.

        Returns:
            The task result on success.

        Raises:
            The last exception if all retries are exhausted.
            asyncio.CancelledError: If cancelled.
        """
        self.reset()
        self._is_running = True
        last_error: Exception | None = None
        delay = self._retry_delay

        try:
            for attempt in range(self._max_retries + 1):
                self._current_attempt = attempt

                if self._cancel_event.is_set():
                    logger.info("ralph_loop_cancelled", attempt=attempt)
                    raise asyncio.CancelledError("Ralph loop was cancelled")

                try:
                    result = await task(*args, **kwargs)
                    logger.info(
                        "ralph_loop_success",
                        attempt=attempt,
                        total_attempts=attempt + 1,
                    )
                    return result

                except asyncio.CancelledError:
                    raise

                except Exception as e:
                    last_error = e
                    logger.warning(
                        "ralph_loop_attempt_failed",
                        attempt=attempt,
                        max_retries=self._max_retries,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                    if attempt >= self._max_retries:
                        break

                    # Call retry callback if provided
                    if on_retry:
                        await on_retry(attempt, e)

                    # Wait before retry (with cancellation check)
                    try:
                        await asyncio.wait_for(
                            self._cancel_event.wait(),
                            timeout=delay,
                        )
                        # If we get here, cancel was requested during wait
                        raise asyncio.CancelledError("Ralph loop was cancelled")
                    except TimeoutError:
                        pass  # Normal timeout, proceed to retry

                    delay = min(delay * self._backoff_factor, self._max_delay)

            # All retries exhausted
            logger.error(
                "ralph_loop_exhausted",
                total_attempts=self._max_retries + 1,
                last_error=str(last_error),
            )
            if last_error:
                raise last_error
            raise RuntimeError("Ralph loop exhausted with no error captured")

        finally:
            self._is_running = False
