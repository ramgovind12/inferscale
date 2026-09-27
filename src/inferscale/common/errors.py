"""OpenAI-style error responses, shared by the gateway and workers."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from inferscale.common.exceptions import InferscaleError
from inferscale.common.logging import logger
from inferscale.common.schemas import ErrorDetail, ErrorResponse


def error_body(
    message: str, error_type: str, *, param: str | None = None, code: str | None = None
) -> ErrorResponse:
    return ErrorResponse(
        error=ErrorDetail(message=message, type=error_type, param=param, code=code)
    )


def error_response(
    status_code: int,
    message: str,
    error_type: str,
    *,
    param: str | None = None,
    code: str | None = None,
) -> JSONResponse:
    body = error_body(message, error_type, param=param, code=code)
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def _inferscale_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, InferscaleError)
    logger.warning(
        "request_failed",
        error=exc.__class__.__name__,
        status=exc.status_code,
        message=exc.message,
    )
    return error_response(exc.status_code, exc.message, exc.error_type, code=exc.code)


async def _validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = [str(p) for p in first.get("loc", ()) if p != "body"]
    message = first.get("msg", "Invalid request")
    if loc:
        message = f"{'.'.join(loc)}: {message}"
    return error_response(400, message, "invalid_request_error", param=".".join(loc) or None)


async def _http_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    error_type = "invalid_request_error" if exc.status_code < 500 else "server_error"
    return error_response(exc.status_code, str(exc.detail), error_type)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InferscaleError, _inferscale_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
