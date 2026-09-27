"""Request-ID propagation: read or create X-Request-ID and bind it to the log context."""

import time
from contextvars import ContextVar

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from inferscale.common.utils import new_request_id

REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = structlog.get_logger(__name__)


def get_request_id() -> str | None:
    """The request ID of the request currently being handled, if any."""
    return request_id_var.get()


class RequestIDMiddleware:
    """
    Pure ASGI middleware (not BaseHTTPMiddleware) so streaming responses are not buffered.

    - Uses the incoming X-Request-ID, or generates one.
    - Binds it to structlog contextvars so every log line carries `request_id`.
    - Echoes it in the response headers and logs one `request_completed` line.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(REQUEST_ID_HEADER) or new_request_id()
        token = request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request_completed",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)
