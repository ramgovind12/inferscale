"""OpenAI-compatible request/response schemas, plus InferScale metadata."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["system", "user", "assistant", "tool", "developer"]
FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]
Priority = Literal["high", "normal", "low"]

# Fields that belong to InferScale, not to the OpenAI API. Stripped before forwarding.
INFERSCALE_FIELDS = frozenset({"priority", "request_id"})


class Message(BaseModel):
    """A single chat message."""

    model_config = ConfigDict(extra="allow")

    role: Role
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None

    def text(self) -> str:
        """Plain-text content, flattening multi-part content."""
        if self.content is None:
            return ""
        if isinstance(self.content, str):
            return self.content
        return " ".join(str(p.get("text", "")) for p in self.content if isinstance(p, dict))


class StreamOptions(BaseModel):
    include_usage: bool = False


class ChatCompletionRequest(BaseModel):
    """Body of POST /v1/chat/completions."""

    # Unknown OpenAI fields (tools, response_format, seed, ...) pass through to the worker.
    model_config = ConfigDict(extra="allow")

    model: str = Field(..., min_length=1)
    messages: list[Message] = Field(..., min_length=1)
    max_tokens: int | None = Field(None, ge=1)
    max_completion_tokens: int | None = Field(None, ge=1)
    temperature: float | None = Field(None, ge=0, le=2)
    top_p: float | None = Field(None, ge=0, le=1)
    n: int = Field(1, ge=1)
    stream: bool = False
    stream_options: StreamOptions | None = None
    stop: str | list[str] | None = None
    presence_penalty: float | None = Field(None, ge=-2, le=2)
    frequency_penalty: float | None = Field(None, ge=-2, le=2)
    user: str | None = None

    # InferScale metadata
    priority: Priority = "normal"
    request_id: str | None = None

    def token_limit(self) -> int | None:
        return self.max_completion_tokens or self.max_tokens

    def to_upstream(self) -> dict[str, Any]:
        """Payload to send to a worker: OpenAI fields only."""
        return self.model_dump(exclude_none=True, exclude=set(INFERSCALE_FIELDS))


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None


class Choice(BaseModel):
    index: int
    message: AssistantMessage
    finish_reason: FinishReason | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


class DeltaMessage(BaseModel):
    role: Literal["assistant"] | None = None
    content: str | None = None


class ChunkChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: FinishReason | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChunkChoice]
    usage: Usage | None = None


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "inferscale"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]


class ErrorDetail(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
