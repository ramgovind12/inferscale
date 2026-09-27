from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from inferscale.common.config import Settings, get_settings
from inferscale.common.errors import error_body, register_error_handlers
from inferscale.common.exceptions import InferscaleError, ModelNotFoundError
from inferscale.common.logging import logger
from inferscale.common.request_id import RequestIDMiddleware, get_request_id
from inferscale.common.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCard,
    ModelList,
)
from inferscale.common.utils import new_request_id
from inferscale.worker.mock import MockEngine

SSE_DONE = b"data: [DONE]\n\n"


def sse_event(payload: str) -> bytes:
    return f"data: {payload}\n\n".encode()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the worker application."""
    settings = settings or get_settings()
    worker_settings = settings.worker
    engine = MockEngine(worker_settings)

    app = FastAPI(title="InferScale Worker")
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def list_models() -> ModelList:
        return ModelList(data=[ModelCard(id=worker_settings.model_name)])

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse | StreamingResponse:
        if request.model != worker_settings.model_name:
            raise ModelNotFoundError(f"Model '{request.model}' is not served by this worker")

        completion_id = f"chatcmpl-{get_request_id() or new_request_id()}"
        logger.info("inference_started", model=request.model, stream=request.stream)

        if not request.stream:
            return await engine.generate(request, completion_id)

        # Pull the first chunk before returning so failures become a proper HTTP error.
        chunks = engine.stream(request, completion_id)
        first = await anext(chunks)
        return StreamingResponse(
            _sse(first, chunks),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app


async def _sse(
    first: ChatCompletionChunk, rest: AsyncIterator[ChatCompletionChunk]
) -> AsyncIterator[bytes]:
    yield sse_event(first.model_dump_json())
    try:
        async for chunk in rest:
            yield sse_event(chunk.model_dump_json())
    except InferscaleError as exc:
        logger.warning("stream_failed", error=exc.__class__.__name__, message=exc.message)
        yield sse_event(error_body(exc.message, exc.error_type).model_dump_json())
    yield SSE_DONE
