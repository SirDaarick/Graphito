"""Evaluation foundation: seeding, normalization, dedup and ground truth for reproducible splits.

The package is import-only and must import without torch.
"""

from .seed import seed_everything, stable_rng

__all__ = ["seed_everything", "stable_rng"]
