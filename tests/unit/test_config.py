from pathlib import Path

import pytest

from inferscale.common.config import CONFIG_PATH_ENV, Settings

YAML = """
gateway:
  port: 8100
  worker_url: http://yaml-worker:9001
worker:
  model_name: yaml-model
  latency_ms: 10
models:
  - id: yaml-model
"""


@pytest.fixture
def yaml_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "inferscale.yaml"
    path.write_text(YAML)
    monkeypatch.setenv(CONFIG_PATH_ENV, str(path))
    return path


def test_defaults_when_config_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV, str(tmp_path / "missing.yaml"))
    settings = Settings()
    assert settings.gateway.port == 8000
    assert settings.worker.model_name == "mock-model"


def test_loads_values_from_yaml(yaml_config: Path) -> None:
    settings = Settings()
    assert settings.gateway.port == 8100
    assert settings.gateway.worker_url == "http://yaml-worker:9001"
    assert settings.worker.model_name == "yaml-model"
    assert settings.worker.latency_ms == 10
    assert [m.id for m in settings.models] == ["yaml-model"]


def test_env_overrides_yaml(yaml_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFERSCALE_GATEWAY__WORKER_URL", "http://env-worker:9001")
    monkeypatch.setenv("INFERSCALE_WORKER__LATENCY_MS", "5")
    settings = Settings()
    assert settings.gateway.worker_url == "http://env-worker:9001"
    assert settings.gateway.port == 8100  # untouched keys still come from YAML
    assert settings.worker.latency_ms == 5
