"""Tests for the --method option of the cluster showcase figure script."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "logic_grouping_eval.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("logic_grouping_eval_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse(script, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["logic_grouping_eval.py", *argv])
    return script.parse_args()


def test_method_defaults_to_v2(script, monkeypatch):
    assert _parse(script, monkeypatch, "--only-cluster-figure").method == "v2"


def test_method_accepts_v2_norm_and_rejects_others(script, monkeypatch):
    assert _parse(script, monkeypatch, "--method", "v2_norm").method == "v2_norm"
    with pytest.raises(SystemExit):
        _parse(script, monkeypatch, "--method", "jaccard")


def test_showcase_json_name_keeps_v2_file(script):
    assert script.cluster_showcase_json_name("v2") == "cluster_showcase.json"
    assert script.cluster_showcase_json_name("v2_norm") == "cluster_showcase_v2norm.json"
