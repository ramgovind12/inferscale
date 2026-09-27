"""Mock inference engine: fake completions with realistic latency and token counts."""

import asyncio
import random
from collections.abc import AsyncIterator

from inferscale.common.config import WorkerSettings
from inferscale.common.exceptions import InferenceError
from inferscale.common.schemas import (
    AssistantMessage,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChunkChoice,
    DeltaMessage,
    FinishReason,
    Usage,
)
from inferscale.common.utils import unix_ts

VOCABULARY = (
    "the model reply token stream latency worker gateway request queue router "
    "inference scale fast system data result value simple mock test output text "
    "answer question context batch cache memory compute signal"
).split()


def count_tokens(text: str) -> int:
    """Rough token count: whitespace-separated words."""
    return len(text.split())


def count_prompt_tokens(request: ChatCompletionRequest) -> int:
    return sum(count_tokens(m.text()) for m in request.messages)


class MockEngine:
    """Generates fake completions at `tokens_per_sec` after `latency_ms` of warm-up."""

    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self._rng = random.Random(settings.seed)

    def plan_tokens(self, request: ChatCompletionRequest) -> tuple[list[str], FinishReason]:
        """Choose the completion tokens and finish reason for a request."""
        natural_length = self.settings.default_max_tokens
        limit = request.token_limit()
        finish_reason: FinishReason = "stop"
        length = natural_length
        if limit is not None and limit < natural_length:
            length, finish_reason = limit, "length"
        words = [self._rng.choice(VOCABULARY) for _ in range(length)]
        # Leading space on every token after the first, like real tokenizers.
        tokens = [w if i == 0 else f" {w}" for i, w in enumerate(words)]
        return tokens, finish_reason

    def _maybe_fail(self) -> None:
        if self._rng.random() < self.settings.failure_rate:
            raise InferenceError("Simulated inference failure")

    def _usage(self, request: ChatCompletionRequest, completion_tokens: int) -> Usage:
        prompt_tokens = count_prompt_tokens(request)
        return Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def generate(
        self, request: ChatCompletionRequest, completion_id: str
    ) -> ChatCompletionResponse:
        self._maybe_fail()
        tokens, finish_reason = self.plan_tokens(request)
        await asyncio.sleep(
            self.settings.latency_ms / 1000 + len(tokens) / self.settings.tokens_per_sec
        )
        return ChatCompletionResponse(
            id=completion_id,
            created=unix_ts(),
            model=self.settings.model_name,
            choices=[
                Choice(
                    index=0,
                    message=AssistantMessage(content="".join(tokens)),
                    finish_reason=finish_reason,
                )
            ],
            usage=self._usage(request, len(tokens)),
        )

    async def stream(
        self, request: ChatCompletionRequest, completion_id: str
    ) -> AsyncIterator[ChatCompletionChunk]:
        self._maybe_fail()
        tokens, finish_reason = self.plan_tokens(request)
        created = unix_ts()

        def chunk(
            delta: DeltaMessage, finish: FinishReason | None = None, usage: Usage | None = None
        ) -> ChatCompletionChunk:
            choices = [] if usage else [ChunkChoice(index=0, delta=delta, finish_reason=finish)]
            return ChatCompletionChunk(
                id=completion_id,
                created=created,
                model=self.settings.model_name,
                choices=choices,
                usage=usage,
            )

        await asyncio.sleep(self.settings.latency_ms / 1000)  # time to first token
        yield chunk(DeltaMessage(role="assistant", content=""))
        interval = 1 / self.settings.tokens_per_sec
        for token in tokens:
            await asyncio.sleep(interval)
            yield chunk(DeltaMessage(content=token))
        yield chunk(DeltaMessage(), finish=finish_reason)
        if request.stream_options and request.stream_options.include_usage:
            yield chunk(DeltaMessage(), usage=self._usage(request, len(tokens)))
