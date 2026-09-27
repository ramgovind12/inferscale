from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from inferscale.common.config import Settings, get_settings
from inferscale.common.errors import register_error_handlers
from inferscale.common.request_id import RequestIDMiddleware
from inferscale.gateway.client import WorkerClient
from inferscale.gateway.routes import chat, models


def create_app(
    settings: Settings | None = None,
    worker_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """
    Build the gateway application.

    `worker_transport` replaces the network transport to workers (tests use ASGITransport).
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.worker_client = WorkerClient(settings.gateway, transport=worker_transport)
        try:
            yield
        finally:
            await app.state.worker_client.aclose()

    app = FastAPI(title="InferScale Gateway", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    app.include_router(chat.router)
    app.include_router(models.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
