from fastapi import FastAPI

from inferscale.common.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the worker application."""
    settings = settings or get_settings()
    app = FastAPI(title="InferScale Worker")
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
