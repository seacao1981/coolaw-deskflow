"""Rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter using sliding window.

    Limits requests per IP address.
    """

    def __init__(
        self,
        app: object,
        requests_per_minute: int = 60,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._rpm = requests_per_minute
        self._window = 60.0  # 1 minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if a client has exceeded the rate limit."""
        now = time.time()
        window_start = now - self._window

        # Clean old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window_start
        ]

        if len(self._requests[client_ip]) >= self._rpm:
            return True

        self._requests[client_ip].append(now)
        return False

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check rate limit before processing request."""
        # Skip health checks
        if request.url.path in ("/api/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        if self._is_rate_limited(client_ip):
            logger.warning("rate_limited", client_ip=client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMITED",
                    "details": {"limit": self._rpm, "window": "1 minute"},
                },
            )

        return await call_next(request)
