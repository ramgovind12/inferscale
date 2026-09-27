from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI

from inferscale.common.config import Settings
from inferscale.gateway.app import create_app as create_gateway
from inferscale.worker.app import create_app as create_worker


@pytest.mark.parametrize("factory", [create_gateway, create_worker])
async def test_health_returns_ok(factory: Callable[[Settings], FastAPI]) -> None:
    app = factory(Settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
