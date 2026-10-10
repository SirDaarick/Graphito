"""Global seeding and keyed deterministic RNG streams."""

import hashlib
import os
import random

import numpy as np


def seed_everything(seed: int, deterministic_torch: bool = False) -> int:
    """Seed `random`, `numpy` and, when installed, `torch`; return the seed for provenance.

    With `deterministic_torch`, torch is also switched to deterministic kernels (best effort:
    non-deterministic ops warn instead of raising).
    """
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return seed

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic_torch:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    return seed


def stable_rng(seed: int, key: str) -> random.Random:
    """Return a `random.Random` derived from (seed, key) via sha256, independent of global state."""
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))
