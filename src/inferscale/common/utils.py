import time
import uuid
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r") as f:
        data = yaml.safe_load(f)
    return data or {}


def new_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex}"


def unix_ts() -> int:
    """Current Unix timestamp in seconds (OpenAI `created` field)."""
    return int(time.time())
