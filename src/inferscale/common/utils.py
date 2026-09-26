from pathlib import Path

import yaml

def load_yaml(path: Path) -> dict:
    with path.open("r") as f:
        return yaml.safe_load(f)