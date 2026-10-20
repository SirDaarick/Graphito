"""Pure helpers of `scripts/contrastive_f1.py` (mean pooling, Accepted-vs-WA AUC, InfoNCE)."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("contrastive_f1", ROOT / "scripts" / "contrastive_f1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


f1 = _load()


def test_mean_pool_positions_averages_only_code_subtokens():
    hidden = torch.zeros(1, 6, 2)
    hidden[0, 0] = 100.0  # CLS
    hidden[0, 1] = torch.tensor([1.0, 3.0])
    hidden[0, 2] = torch.tensor([3.0, 5.0])
    hidden[0, 3] = 100.0  # SEP
    hidden[0, 4:] = 100.0  # DFG nodes and padding
    pooled = f1.mean_pool_positions(hidden, [2])
    assert torch.allclose(pooled, torch.tensor([[2.0, 4.0]]))


def test_accepted_vs_wa_auc_is_one_when_accepted_are_closer_than_wrong_answers():
    problems = ["p"] * 5
    roles = ["accepted", "accepted", "accepted", "wrong_answer", "wrong_answer"]
    sim = np.full((5, 5), 0.1)
    sim[:3, :3] = 0.9
    res = f1.accepted_vs_wa_auc(sim, problems, roles)
    assert res["pooled_auc"] == pytest.approx(1.0)
    assert res["n_problems"] == 1


def test_accepted_vs_wa_auc_is_half_for_constant_similarity():
    problems = ["p"] * 4
    roles = ["accepted", "accepted", "wrong_answer", "wrong_answer"]
    res = f1.accepted_vs_wa_auc(np.ones((4, 4)), problems, roles)
    assert res["pooled_auc"] == pytest.approx(0.5)


def test_accepted_vs_wa_auc_skips_problems_without_wrong_answers():
    res = f1.accepted_vs_wa_auc(np.ones((2, 2)), ["p", "p"], ["accepted", "accepted"])
    assert res == {"pooled_auc": None, "mean_problem_auc": None, "n_problems": 0}


def test_info_nce_is_low_for_matched_pairs_and_high_for_mismatched_ones():
    eye = torch.eye(4)
    matched = f1.info_nce(eye, eye)
    mismatched = f1.info_nce(eye, eye.roll(1, dims=0))
    assert matched.item() < 0.01
    assert mismatched.item() > matched.item() + 1.0
