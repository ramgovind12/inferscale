"""Gateway + mock worker, in-process (no network)."""

import json
from typing import Any

import httpx
import httpx2
import openai
from structlog.testing import LogCapture

from tests.integration.conftest import gateway_client, running_gateway

CHAT = "/v1/chat/completions"


def chat_body(**overrides: Any) -> dict[str, Any]:
    return {
        "model": "mock-model",
        "messages": [{"role": "user", "content": "hi there"}],
    } | overrides


def parse_sse(text: str) -> list[str]:
    return [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]


async def test_non_streaming_completion(client: httpx.AsyncClient) -> None:
    resp = await client.post(CHAT, json=chat_body())
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "mock-model"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"] == {"prompt_tokens": 2, "completion_tokens": 8, "total_tokens": 10}


async def test_streaming_completion(client: httpx.AsyncClient) -> None:
    body = chat_body(stream=True, stream_options={"include_usage": True})
    async with client.stream("POST", CHAT, json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = parse_sse((await resp.aread()).decode())

    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    text = "".join(c["choices"][0]["delta"]["content"] or "" for c in chunks if c["choices"])
    assert len(text.split()) == 8
    assert chunks[-1]["usage"]["completion_tokens"] == 8


async def test_request_id_propagates_to_worker_and_response(
    client: httpx.AsyncClient, logs: LogCapture
) -> None:
    resp = await client.post(CHAT, json=chat_body(), headers={"X-Request-ID": "trace-123"})
    assert resp.headers["X-Request-ID"] == "trace-123"
    assert resp.json()["id"] == "chatcmpl-trace-123"

    events = {e["event"]: e for e in logs.entries}
    assert events["forwarding_request"]["request_id"] == "trace-123"  # gateway
    # The worker middleware re-binds request_id from the header it receives, so this only
    # matches if the gateway forwarded it.
    assert events["inference_started"]["request_id"] == "trace-123"


async def test_request_id_generated_when_missing(client: httpx.AsyncClient) -> None:
    resp = await client.post(CHAT, json=chat_body())
    assert resp.headers["X-Request-ID"].startswith("req_")


async def test_list_models(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/models")
    assert resp.status_code == 200
    assert resp.json() == {
        "object": "list",
        "data": [{"id": "mock-model", "object": "model", "created": 0, "owned_by": "inferscale"}],
    }


async def test_invalid_body_returns_openai_error(client: httpx.AsyncClient) -> None:
    resp = await client.post(CHAT, json={"model": "mock-model", "messages": []})
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["type"] == "invalid_request_error"
    assert error["param"] == "messages"


async def test_unknown_model_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.post(CHAT, json=chat_body(model="gpt-9"))
    assert resp.status_code == 404
    assert "gpt-9" in resp.json()["error"]["message"]


async def test_worker_failure_returns_502() -> None:
    async with gateway_client(worker={"failure_rate": 1.0}) as client:
        for stream in (False, True):
            resp = await client.post(CHAT, json=chat_body(stream=stream))
            assert resp.status_code == 502
            assert "Simulated inference failure" in resp.json()["error"]["message"]


async def test_unreachable_worker_returns_502() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with gateway_client(transport=httpx.MockTransport(refuse)) as client:
        resp = await client.post(CHAT, json=chat_body())
    assert resp.status_code == 502
    assert "unreachable" in resp.json()["error"]["message"]


async def test_slow_worker_returns_504() -> None:
    async with gateway_client(
        worker={"latency_ms": 2000}, gateway={"request_timeout_s": 0.05}
    ) as client:
        for stream in (False, True):
            resp = await client.post(CHAT, json=chat_body(stream=stream))
            assert resp.status_code == 504
            assert resp.json()["error"]["type"] == "timeout_error"


async def test_worker_4xx_passes_through() -> None:
    def reject(request: httpx.Request) -> httpx.Response:
        body = {"error": {"message": "context too long", "type": "invalid_request_error"}}
        return httpx.Response(400, json=body)

    async with gateway_client(transport=httpx.MockTransport(reject)) as client:
        resp = await client.post(CHAT, json=chat_body())
    assert resp.status_code == 400
    assert resp.json()["error"]["message"] == "context too long"


async def test_official_openai_sdk() -> None:
    async with running_gateway() as app:
        http_client = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app))
        sdk = openai.AsyncOpenAI(base_url="http://gw/v1", api_key="unused", http_client=http_client)
        async with sdk:
            completion = await sdk.chat.completions.create(
                model="mock-model", messages=[{"role": "user", "content": "hi"}]
            )
            assert completion.choices[0].message.content
            assert completion.usage is not None
            assert completion.usage.completion_tokens == 8

            stream = await sdk.chat.completions.create(
                model="mock-model", messages=[{"role": "user", "content": "hi"}], stream=True
            )
            parts = [c.choices[0].delta.content or "" async for c in stream if c.choices]
            assert len("".join(parts).split()) == 8

            models = await sdk.models.list()
            assert [m.id for m in models.data] == ["mock-model"]
