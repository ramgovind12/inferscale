from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import structlog
from fastapi import FastAPI
from structlog.testing import LogCapture

from inferscale.common.config import Settings
from inferscale.gateway.app import create_app as create_gateway
from inferscale.worker.app import create_app as create_worker

FAST_WORKER = {"latency_ms": 0, "tokens_per_sec": 100_000, "default_max_tokens": 8, "seed": 1}


def make_settings(
    worker: dict[str, Any] | None = None, gateway: dict[str, Any] | None = None
) -> Settings:
    return Settings.model_validate(
        {
            "worker": FAST_WORKER | (worker or {}),
            "gateway": {"worker_url": "http://worker"} | (gateway or {}),
            "models": [{"id": "mock-model"}],
        }
    )


@asynccontextmanager
async def running_gateway(
    worker: dict[str, Any] | None = None,
    gateway: dict[str, Any] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[FastAPI]:
    """
    An in-process gateway (lifespan running) wired to an in-process mock worker through
    httpx.ASGITransport. Pass `transport=` to replace the worker (e.g. an httpx.MockTransport).
    """
    settings = make_settings(worker, gateway)
    worker_transport = transport or httpx.ASGITransport(app=create_worker(settings))
    app = create_gateway(settings, worker_transport=worker_transport)
    async with app.router.lifespan_context(app):
        yield app


@asynccontextmanager
async def gateway_client(
    worker: dict[str, Any] | None = None,
    gateway: dict[str, Any] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    async with (
        running_gateway(worker, gateway, transport) as app,
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gw") as client,
    ):
        yield client


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with gateway_client() as c:
        yield c


@pytest.fixture
def logs() -> Iterator[LogCapture]:
    """Capture structlog events, including context-bound fields such as request_id."""
    capture = LogCapture()
    old = structlog.get_config()
    structlog.configure(processors=[structlog.contextvars.merge_contextvars, capture])
    try:
        yield capture
    finally:
        structlog.configure(**old)
