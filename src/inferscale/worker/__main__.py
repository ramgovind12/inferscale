import uvicorn

from inferscale.common.config import get_settings
from inferscale.common.logging import setup_logging
from inferscale.worker.app import create_app


def main() -> None:
    settings = get_settings()
    setup_logging(settings.logging.level, service="worker")
    uvicorn.run(
        create_app(settings),
        host=settings.worker.host,
        port=settings.worker.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
