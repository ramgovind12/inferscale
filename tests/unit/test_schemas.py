import pytest
from pydantic import ValidationError

from inferscale.common.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChunkChoice,
    DeltaMessage,
    Message,
)


def make_request(**overrides: object) -> ChatCompletionRequest:
    body: dict[str, object] = {
        "model": "mock-model",
        "messages": [{"role": "user", "content": "hi"}],
    }
    body.update(overrides)
    return ChatCompletionRequest.model_validate(body)


def test_request_defaults() -> None:
    req = make_request()
    assert req.stream is False
    assert req.n == 1
    assert req.priority == "normal"
    assert req.request_id is None
    assert req.messages[0].text() == "hi"


@pytest.mark.parametrize(
    "overrides",
    [
        {"messages": []},
        {"model": ""},
        {"temperature": 3},
        {"max_tokens": 0},
        {"priority": "urgent"},
        {"messages": [{"role": "robot", "content": "hi"}]},
    ],
)
def test_request_validation_errors(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_unknown_openai_fields_pass_through_and_inferscale_fields_are_stripped() -> None:
    req = make_request(seed=7, response_format={"type": "text"}, priority="high", request_id="r1")
    upstream = req.to_upstream()
    assert upstream["seed"] == 7
    assert upstream["response_format"] == {"type": "text"}
    assert "priority" not in upstream
    assert "request_id" not in upstream
    assert "temperature" not in upstream  # None values are not forwarded


def test_token_limit_prefers_max_completion_tokens() -> None:
    assert make_request(max_tokens=10).token_limit() == 10
    assert make_request(max_tokens=10, max_completion_tokens=5).token_limit() == 5
    assert make_request().token_limit() is None


def test_multipart_content_text() -> None:
    msg = Message(
        role="user", content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    )
    assert msg.text() == "a b"


def test_chunk_serialization() -> None:
    chunk = ChatCompletionChunk(
        id="c1",
        created=1,
        model="m",
        choices=[ChunkChoice(index=0, delta=DeltaMessage(content="x"))],
    )
    data = chunk.model_dump()
    assert data["object"] == "chat.completion.chunk"
    assert data["choices"][0]["delta"]["content"] == "x"
    assert data["choices"][0]["finish_reason"] is None
