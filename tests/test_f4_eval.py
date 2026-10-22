"""Pure helpers of `scripts/f4_eval.py` (verdict rules, reproduction gate, frozen-run guard)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("f4_eval", ROOT / "scripts" / "f4_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


f4 = _load()


@pytest.mark.parametrize(
    "ci, expected",
    [([0.01, 0.05], "confirmed"), ([-0.02, 0.03], "inconclusive"), ([-0.05, -0.01], "refuted"), ([0.0, 0.04], "inconclusive"), (None, "inconclusive")],
)
def test_improvement_verdict_uses_the_ci_against_zero(ci, expected):
    assert f4.improvement_verdict(ci) == expected


def test_non_regression_verdict_is_refuted_only_by_a_ci_entirely_below_zero():
    ok = {"T1": {"value": 0.02, "ci95": [-0.01, 0.05]}, "T5": {"value": 0.0, "ci95": [-0.02, 0.02]}}
    assert f4.non_regression_verdict(ok)["verdict"] == "confirmed"
    bad = {**ok, "T6": {"value": -0.05, "ci95": [-0.08, -0.02]}}
    res = f4.non_regression_verdict(bad)
    assert res["verdict"] == "refuted" and res["refuted_conditions"] == ["T6"]


def test_non_regression_verdict_ignores_missing_conditions_but_reports_them():
    res = f4.non_regression_verdict({"T1": {"value": 0.01, "ci95": [0.0, 0.02]}, "T2": None})
    assert res["verdict"] == "confirmed" and res["missing_conditions"] == ["T2"]


def test_reproduces_uses_an_absolute_tolerance():
    assert f4.reproduces(0.3790044, 0.37900444457846694, 1e-6)
    assert not f4.reproduces(0.3800, 0.37900444457846694, 1e-6)
    assert not f4.reproduces(None, 0.5, 1e-6)


def test_paired_difference_aligns_by_key_and_treats_none_as_zero():
    a = {"x": 0.5, "y": None, "z": 0.7}
    b = {"x": 0.4, "y": 0.1, "w": 0.9}  # only x and y are shared
    res = f4.paired_difference(a, b, n_boot=200, seed=1)
    assert res["n_units"] == 2
    assert res["mean_diff"] == pytest.approx(((0.5 - 0.4) + (0.0 - 0.1)) / 2)
    assert len(res["ci95"]) == 2


def test_frozen_guard_refuses_a_second_run_unless_resuming(tmp_path):
    frozen = {"adapters": {"ft_B_s1": "a" * 64}, "headline": "ft_B_s1"}
    assert f4.check_frozen(tmp_path, frozen, resume=False) == "created"
    assert json.loads((tmp_path / "f4_frozen.json").read_text(encoding="utf-8"))["headline"] == "ft_B_s1"
    with pytest.raises(SystemExit):
        f4.check_frozen(tmp_path, frozen, resume=False)
    assert f4.check_frozen(tmp_path, frozen, resume=True) == "resumed"


def test_frozen_guard_refuses_to_resume_with_different_adapters(tmp_path):
    f4.check_frozen(tmp_path, {"adapters": {"ft_B_s1": "a" * 64}, "headline": "ft_B_s1"}, resume=False)
    with pytest.raises(SystemExit):
        f4.check_frozen(tmp_path, {"adapters": {"ft_B_s1": "b" * 64}, "headline": "ft_B_s1"}, resume=True)
