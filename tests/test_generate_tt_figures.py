"""Tests for scripts/generate_tt_figures.py (SC1.1): figures come from run metrics, never literals."""

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "generate_tt_figures.py"

sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("generate_tt_figures", SCRIPT)
figs = importlib.util.module_from_spec(_spec)
sys.modules["generate_tt_figures"] = figs
_spec.loader.exec_module(figs)

GCB_METHODS = ("v2", "v2_nodfg", "jaccard", "winnowing", "legacy")


def _metric(value, ci=(0.1, 0.2)):
    return {"value": value, "ci95": list(ci) if ci is not None else None}


def _charcnn_metrics():
    return {
        "schema": "graphito.metrics/v1",
        "channel": "char_cnn",
        "selected_epoch": 3,
        "operating_points": {
            "fpr_0.01": {
                "primary": False,
                "threshold": 0.4,
                "observed": {"tp": 1, "fp": 2, "fn": 3, "tn": 4},
            },
            "fpr_0.05": {
                "primary": True,
                "threshold": 0.25,
                "observed": {"tp": 11, "fp": 7, "fn": 5, "tn": 77},
            },
        },
        "threshold_free": {"roc_auc": _metric(0.111), "pr_auc": _metric(0.222)},
    }


def _gcb_metrics(i):
    return {
        "schema": "graphito.metrics/v1",
        "channel": "graphcodebert",
        "threshold_free": {
            "roc_auc": _metric(0.5 + i / 100),
            "pr_auc": _metric(0.01 * (i + 1)),
            "map_at_r": _metric(0.2 + i / 100, ci=None),
        },
    }


@pytest.fixture
def runs(tmp_path):
    charcnn = tmp_path / "runs" / "char_cnn" / "r1"
    charcnn.mkdir(parents=True)
    (charcnn / "metrics.json").write_text(json.dumps(_charcnn_metrics()), encoding="utf-8")
    (charcnn / "history.csv").write_text(
        "epoch,train_loss,val_roc_auc,val_pr_auc\n0,1.5,0.9,0.7\n1,0.8,0.95,0.8\n2,0.6,0.96,0.85\n",
        encoding="utf-8",
    )
    gcb = tmp_path / "runs" / "graphcodebert" / "r2"
    for i, method in enumerate(GCB_METHODS):
        d = gcb / f"{method}__all"
        d.mkdir(parents=True)
        (d / "metrics.json").write_text(json.dumps(_gcb_metrics(i)), encoding="utf-8")
    return charcnn, gcb


def test_charcnn_loader_returns_fixture_values(runs):
    charcnn, _ = runs
    run = figs.load_charcnn_run(charcnn)
    assert run.metrics["threshold_free"]["roc_auc"]["value"] == 0.111
    assert run.history is not None
    assert list(run.history["epoch"]) == [0, 1, 2]


def test_confusion_uses_primary_operating_point(runs):
    charcnn, _ = runs
    cm = figs.confusion_from_metrics(figs.load_charcnn_run(charcnn).metrics)
    assert cm.key == "fpr_0.05"
    assert cm.threshold == 0.25
    assert (cm.tn, cm.fp, cm.fn, cm.tp) == (77, 7, 5, 11)


def test_gcb_loader_reads_every_method(runs):
    _, gcb = runs
    rows = figs.load_gcb_run(gcb)
    assert [r.method for r in rows] == list(GCB_METHODS)
    assert rows[2].roc_auc == pytest.approx(0.52)
    assert rows[2].roc_auc_ci == (0.1, 0.2)
    assert rows[0].map_at_r == pytest.approx(0.2)
    assert rows[0].map_at_r_ci is None


def test_missing_charcnn_run_is_a_clear_error(tmp_path):
    with pytest.raises(figs.RunNotFoundError, match="metrics.json"):
        figs.load_charcnn_run(tmp_path / "nope")


def test_missing_gcb_method_is_a_clear_error(runs):
    _, gcb = runs
    (gcb / "legacy__all" / "metrics.json").unlink()
    with pytest.raises(figs.RunNotFoundError, match="legacy__all"):
        figs.load_gcb_run(gcb)


def test_missing_history_is_reported_not_faked(runs, tmp_path, capsys):
    charcnn, gcb = runs
    (charcnn / "history.csv").unlink()
    run = figs.load_charcnn_run(charcnn)
    assert run.history is None
    out = tmp_path / "out"
    assert figs.main(["--charcnn-run", str(charcnn), "--gcb-run", str(gcb), "--out-dir", str(out)]) == 0
    assert "history.csv" in capsys.readouterr().out
    assert not (out / figs.CURVES_FIGURE).exists()
    assert (out / figs.CONFUSION_FIGURE).exists()
    assert (out / figs.CHANNEL_A_FIGURE).exists()


def test_main_writes_all_figures(runs, tmp_path):
    charcnn, gcb = runs
    out = tmp_path / "out"
    assert figs.main(["--charcnn-run", str(charcnn), "--gcb-run", str(gcb), "--out-dir", str(out)]) == 0
    for name in (figs.CURVES_FIGURE, figs.CONFUSION_FIGURE, figs.CHANNEL_A_FIGURE):
        assert (out / name).stat().st_size > 0


def test_main_missing_run_exits_nonzero(runs, tmp_path, capsys):
    _, gcb = runs
    code = figs.main(["--charcnn-run", str(tmp_path / "missing"), "--gcb-run", str(gcb), "--out-dir", str(tmp_path)])
    assert code != 0
    assert "metrics.json" in capsys.readouterr().err


def test_run_arguments_are_required():
    with pytest.raises(SystemExit) as exc:
        figs.main([])
    assert exc.value.code == 2


def test_script_has_no_hardcoded_metric_literals():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in ("base_scores", "lora_scores", "p_ai"):
        assert name not in source
    assert "models.char_cnn.train" not in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            # Style constants (alpha, widths) use at most two decimals; metric values use more.
            assert len(repr(node.value).split(".")[-1]) <= 2, f"metric-like literal {node.value!r}"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not re.search(r"\d+\.\d{2,}\s*%|F1:\s*0\.\d", node.value), f"metric-like text {node.value!r}"
