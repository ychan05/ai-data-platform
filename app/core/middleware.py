import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Manages request context for looging and tracking"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Create a request ID for logging/tracking purposes. If the client provides one, use it; otherwise, generate a new one.
        request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # Attach request info to the logging context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()

        response = await call_next(request)

        # Record the log entry and latency
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        logger.info(
            "http.request.completed",
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        # Add the request ID to the response headers for client-side tracking
        response.headers["X-Request-Id"] = request_id
        return response