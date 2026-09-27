"""HTTP client the gateway uses to talk to workers."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from inferscale.common.config import GatewaySettings
from inferscale.common.exceptions import (
    InferenceError,
    InferenceTimeoutError,
    WorkerUnavailableError,
)
from inferscale.common.request_id import REQUEST_ID_HEADER

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"


class WorkerClient:
    """
    Wraps one shared httpx.AsyncClient for all worker calls.

    Worker 4xx responses are returned to the caller unchanged (the client made the mistake).
    Timeouts become InferenceTimeoutError (504); connection errors and worker 5xx become
    WorkerUnavailableError / InferenceError (502).
    """

    def __init__(
        self, settings: GatewaySettings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.base_url = settings.worker_url
        self.request_timeout_s = settings.request_timeout_s
        self._client = httpx.AsyncClient(
            base_url=settings.worker_url,
            timeout=httpx.Timeout(settings.request_timeout_s, connect=settings.connect_timeout_s),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat_completion(self, payload: dict[str, Any], request_id: str) -> httpx.Response:
        """Non-streaming call. Returns the worker response (2xx or 4xx)."""
        request = self._build_request(payload, request_id)
        response = await self._send(request, stream=False)
        await _raise_for_server_error(response)
        return response

    async def open_stream(self, payload: dict[str, Any], request_id: str) -> httpx.Response:
        """
        Streaming call. Returns once the worker has sent its response headers; the caller
        must consume the body with `iter_stream` (which closes it) or call `aclose()`.
        """
        request = self._build_request(payload, request_id)
        response = await self._send(request, stream=True)
        if response.status_code >= 400:
            await response.aread()
            await response.aclose()
        await _raise_for_server_error(response)
        return response

    async def iter_stream(self, response: httpx.Response) -> AsyncIterator[bytes]:
        """Yield raw SSE bytes from an open stream, mapping transport errors."""
        try:
            async for data in response.aiter_raw():
                yield data
        except httpx.TimeoutException as exc:
            raise InferenceTimeoutError("Worker stream timed out") from exc
        except httpx.TransportError as exc:
            raise WorkerUnavailableError(f"Worker stream failed: {exc}") from exc
        finally:
            await response.aclose()

    def _build_request(self, payload: dict[str, Any], request_id: str) -> httpx.Request:
        return self._client.build_request(
            "POST",
            CHAT_COMPLETIONS_PATH,
            json=payload,
            headers={REQUEST_ID_HEADER: request_id},
        )

    async def _send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
        # asyncio.timeout bounds the wait for the worker's response headers (the whole body when
        # not streaming); httpx's own timeouts additionally bound connect and each read.
        try:
            async with asyncio.timeout(self.request_timeout_s):
                return await self._client.send(request, stream=stream)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise InferenceTimeoutError(
                f"Worker did not respond within {self.request_timeout_s}s"
            ) from exc
        except httpx.TransportError as exc:
            raise WorkerUnavailableError(
                f"Worker at {self.base_url} is unreachable: {exc}"
            ) from exc


async def _raise_for_server_error(response: httpx.Response) -> None:
    if response.status_code < 500:
        return
    message = f"Worker returned HTTP {response.status_code}"
    try:
        detail = response.json()["error"]["message"]
        message = f"{message}: {detail}"
    except (ValueError, KeyError, TypeError):
        pass
    raise InferenceError(message)
