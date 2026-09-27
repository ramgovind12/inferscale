from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from inferscale.common.config import Settings
from inferscale.common.errors import error_body
from inferscale.common.exceptions import InferscaleError, ModelNotFoundError
from inferscale.common.logging import logger
from inferscale.common.request_id import get_request_id
from inferscale.common.schemas import ChatCompletionRequest
from inferscale.common.utils import new_request_id
from inferscale.gateway.client import WorkerClient

router = APIRouter()


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(body: ChatCompletionRequest, request: Request) -> Response:
    settings: Settings = request.app.state.settings
    client: WorkerClient = request.app.state.worker_client

    if body.model not in {m.id for m in settings.models}:
        raise ModelNotFoundError(f"The model '{body.model}' does not exist")

    request_id = get_request_id() or new_request_id()
    payload = body.to_upstream()
    logger.info(
        "forwarding_request",
        model=body.model,
        stream=body.stream,
        priority=body.priority,
        worker=client.base_url,
    )

    if not body.stream:
        upstream = await client.chat_completion(payload, request_id)
        return _passthrough(upstream)

    upstream = await client.open_stream(payload, request_id)
    if upstream.status_code >= 400:
        return _passthrough(upstream)
    return StreamingResponse(
        _relay(client, upstream),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _passthrough(upstream: httpx.Response) -> Response:
    try:
        return JSONResponse(status_code=upstream.status_code, content=upstream.json())
    except ValueError:
        return Response(
            status_code=upstream.status_code,
            content=upstream.content,
            media_type=upstream.headers.get("content-type"),
        )


async def _relay(client: WorkerClient, upstream: httpx.Response) -> AsyncIterator[bytes]:
    """Relay worker SSE bytes; a mid-stream failure becomes an SSE error event."""
    try:
        async for data in client.iter_stream(upstream):
            yield data
    except InferscaleError as exc:
        logger.warning("stream_failed", error=exc.__class__.__name__, message=exc.message)
        error = error_body(exc.message, exc.error_type).model_dump_json()
        yield f"data: {error}\n\ndata: [DONE]\n\n".encode()
