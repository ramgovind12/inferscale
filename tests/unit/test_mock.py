import pytest

from inferscale.common.config import WorkerSettings
from inferscale.common.exceptions import InferenceError
from inferscale.common.schemas import ChatCompletionChunk, ChatCompletionRequest
from inferscale.worker.mock import MockEngine, count_prompt_tokens, count_tokens


def fast_engine(**overrides: object) -> MockEngine:
    settings = WorkerSettings.model_validate(
        {"latency_ms": 0, "tokens_per_sec": 100_000, "default_max_tokens": 8, "seed": 1} | overrides
    )
    return MockEngine(settings)


def make_request(**overrides: object) -> ChatCompletionRequest:
    body: dict[str, object] = {
        "model": "mock-model",
        "messages": [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hello there world"},
        ],
    }
    body.update(overrides)
    return ChatCompletionRequest.model_validate(body)


def test_count_tokens() -> None:
    assert count_tokens("") == 0
    assert count_tokens("one two  three") == 3
    assert count_prompt_tokens(make_request()) == 5


async def test_generate_returns_usage_and_stop() -> None:
    resp = await fast_engine().generate(make_request(), "chatcmpl-1")
    content = resp.choices[0].message.content
    assert content is not None
    assert resp.id == "chatcmpl-1"
    assert resp.model == "mock-model"
    assert resp.choices[0].finish_reason == "stop"
    assert resp.usage.prompt_tokens == 5
    assert resp.usage.completion_tokens == 8 == count_tokens(content)
    assert resp.usage.total_tokens == 13


async def test_generate_respects_max_tokens() -> None:
    resp = await fast_engine().generate(make_request(max_tokens=3), "c")
    assert resp.usage.completion_tokens == 3
    assert resp.choices[0].finish_reason == "length"


async def test_seeded_output_is_deterministic() -> None:
    a = await fast_engine().generate(make_request(), "c")
    b = await fast_engine().generate(make_request(), "c")
    assert a.choices[0].message.content == b.choices[0].message.content


async def collect(engine: MockEngine, request: ChatCompletionRequest) -> list[ChatCompletionChunk]:
    return [chunk async for chunk in engine.stream(request, "c")]


async def test_stream_chunk_order() -> None:
    chunks = await collect(fast_engine(), make_request(stream=True))
    first, *tokens, last = chunks
    assert first.choices[0].delta.role == "assistant"
    assert len(tokens) == 8
    assert all(c.choices[0].delta.content for c in tokens)
    assert all(c.choices[0].finish_reason is None for c in tokens)
    assert last.choices[0].finish_reason == "stop"
    assert all(c.usage is None for c in chunks)


async def test_stream_include_usage_appends_usage_chunk() -> None:
    request = make_request(stream=True, max_tokens=2, stream_options={"include_usage": True})
    chunks = await collect(fast_engine(), request)
    assert chunks[-2].choices[0].finish_reason == "length"
    usage_chunk = chunks[-1]
    assert usage_chunk.choices == []
    assert usage_chunk.usage is not None
    assert usage_chunk.usage.completion_tokens == 2


async def test_failure_rate_one_always_fails() -> None:
    engine = fast_engine(failure_rate=1.0)
    with pytest.raises(InferenceError):
        await engine.generate(make_request(), "c")
    with pytest.raises(InferenceError):
        await collect(engine, make_request(stream=True))
