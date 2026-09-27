import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_PATH_ENV = "INFERSCALE_CONFIG"
DEFAULT_CONFIG_PATH = Path("config/inferscale.yaml")


class GatewaySettings(BaseModel):
    """Settings for the gateway (control plane) process."""

    host: str = "0.0.0.0"
    port: int = 8000
    worker_url: str = "http://localhost:9001"
    connect_timeout_s: float = Field(5.0, gt=0)
    request_timeout_s: float = Field(60.0, gt=0)


class WorkerSettings(BaseModel):
    """Settings for a mock worker process."""

    host: str = "0.0.0.0"
    port: int = 9001
    model_name: str = "mock-model"
    latency_ms: float = Field(200.0, ge=0)
    tokens_per_sec: float = Field(50.0, gt=0)
    failure_rate: float = Field(0.0, ge=0, le=1)
    default_max_tokens: int = Field(64, ge=1)
    seed: int | None = None


class LoggingSettings(BaseModel):
    """Settings for structured logging."""

    level: str = "INFO"


class ModelEntry(BaseModel):
    """A model exposed through GET /v1/models."""

    id: str
    owned_by: str = "inferscale"


class Settings(BaseSettings):
    """
    Top-level InferScale settings.

    Priority (highest first): init kwargs > env vars (INFERSCALE_*) > YAML file > defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="INFERSCALE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    gateway: GatewaySettings = GatewaySettings()
    worker: WorkerSettings = WorkerSettings()
    logging: LoggingSettings = LoggingSettings()
    models: list[ModelEntry] = [ModelEntry(id="mock-model")]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_path = Path(os.environ.get(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH))
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=yaml_path),
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once."""
    return Settings()
