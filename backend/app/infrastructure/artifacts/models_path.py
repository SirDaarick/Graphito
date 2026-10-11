"""The one place that puts the repository root on `sys.path` so infrastructure can import the
top-level `models` package (design D4). In the container the root is `/` and `./models` is
mounted read-only at `/models`."""

import sys
from pathlib import Path

# backend/app/infrastructure/artifacts/models_path.py -> repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def ensure_on_path() -> Path:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT
