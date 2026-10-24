"""Pure helpers of `scripts/contrastive_train.py` (F2 pilot: triplet InfoNCE and batch planning)."""

import importlib.util
import random
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]


def _load():
    sys.path.insert(0, str(ROOT / "scripts"))  # contrastive_train imports contrastive_f1 as a sibling
    spec = importlib.util.spec_from_file_location("contrastive_train", ROOT / "scripts" / "contrastive_train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ct = _load()


def test_hard_negative_close_to_the_anchor_raises_the_loss():
    eye = torch.eye(4)
    far = ct.info_nce_hard(eye, eye, negatives=torch.zeros(4, 4))  # orthogonal to every anchor
    near = ct.info_nce_hard(eye, eye, negatives=eye)  # the negative of anchor i is anchor i itself
    assert near.item() > far.item() + 0.5  # near ~ ln 2 (positive and negative tie), far ~ 0


def test_without_negatives_only_the_batch_positives_compete():
    eye = torch.eye(4)
    assert ct.info_nce_hard(eye, eye, negatives=None).item() < 0.01
    assert ct.info_nce_hard(eye, eye.roll(1, dims=0), negatives=None).item() > 1.0


def test_hard_negatives_are_extra_candidates_not_extra_anchors():
    eye = torch.eye(4)
    # a negative orthogonal to every anchor adds candidates but must not break the matched pairs
    ortho = torch.zeros(4, 4)
    ortho[:, 0] = 0.0
    with_neg = ct.info_nce_hard(eye, eye, negatives=ortho)
    without = ct.info_nce_hard(eye, eye, negatives=None)
    assert with_neg.item() >= without.item() - 1e-6


def test_problem_batches_have_distinct_problems_and_even_coverage():
    problems = [f"p{i}" for i in range(10)]
    batches = ct.problem_batches(problems, batch_size=4, n_steps=25, rng=random.Random(0))
    assert len(batches) == 25
    assert all(len(set(b)) == 4 for b in batches)
    counts = {p: sum(p in b for b in batches) for p in problems}
    assert max(counts.values()) - min(counts.values()) <= 1


def test_problem_batches_rejects_batches_larger_than_the_pool():
    with pytest.raises(ValueError):
        ct.problem_batches(["a", "b"], batch_size=3, n_steps=1, rng=random.Random(0))
