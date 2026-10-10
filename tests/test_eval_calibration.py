"""Calibration: val-only fitting, calibrators, FPR-targeted thresholds and the calibration file."""

import hashlib
import json
import os
import re

import numpy as np
import pytest

from models.evaluation import calibration as C
from models.evaluation import provenance as P
from models.evaluation.metrics import roc_auc

SHA = "a" * 64


def _val_set(n=2000, seed=0, split="val", entry_splits=None):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    z = rng.normal(0, 1.5, n) + 1.2 * (2 * y - 1)
    scores = 1 / (1 + np.exp(-z))
    ids = [f"A2016/Z1/Z1/student{i:04d}.c" for i in range(n)]
    return C.ScoredSet(ids, scores, y, split=split, manifest_sha256=SHA, entry_splits=entry_splits)


class _FakeManifest:
    def __init__(self, splits, sha256=SHA):
        self._splits = splits
        self.sha256 = sha256

    def split_of(self, sample_id):
        return self._splits[sample_id]


# --- val-only fitting -----------------------------------------------------------------------


def test_fit_rejects_split_tag_other_than_val():
    data = _val_set(50, split="test")
    with pytest.raises(ValueError, match="val"):
        C.fit(data)


def test_fit_rejects_any_non_val_entry_and_writes_nothing(tmp_path):
    data = _val_set(50, entry_splits=["val"] * 49 + ["test"])
    out = tmp_path / "calibration.json"
    with pytest.raises(ValueError, match=re.escape(data.ids[-1])):
        artifact, _ = C.build_calibration(data, channel="channel_b", score_name="ai_prob", seed=1)
        C.save_calibration(artifact, out)
    assert not out.exists() and list(tmp_path.iterdir()) == []


def test_fit_checks_every_id_against_the_manifest():
    data = _val_set(20)
    splits = {i: "val" for i in data.ids}
    C.fit(data, manifest=_FakeManifest(splits))
    splits[data.ids[3]] = "train"
    with pytest.raises(ValueError, match="train"):
        C.fit(data, manifest=_FakeManifest(splits))
    with pytest.raises(ValueError, match="sha256"):
        C.fit(data, manifest=_FakeManifest({i: "val" for i in data.ids}, sha256="b" * 64))


def test_scored_set_from_samples_takes_entry_splits():
    class S:
        def __init__(self, i, split):
            self.id, self.split = i, split

    samples = [S("x", "val"), S("y", "test")]
    data = C.ScoredSet.from_samples(samples, [0.2, 0.7], [0, 1], manifest_sha256=SHA)
    assert data.entry_splits == ("val", "test") and data.split == "mixed"
    with pytest.raises(ValueError, match="'y'"):
        C.fit(data)


# --- calibrators ----------------------------------------------------------------------------


@pytest.mark.parametrize("method", C.METHODS)
def test_calibrators_preserve_ranking(method):
    data = _val_set()
    cal = C.fit(data, method)
    grid = np.linspace(0.01, 0.99, 99)
    p = cal.transform(grid)
    assert np.all((p >= 0) & (p <= 1))
    assert np.all(np.diff(p) >= 0)  # isotonic may tie (plateaus); never inverts
    if method != "isotonic":
        assert np.all(np.diff(p) > 0)
        assert roc_auc(data.y, cal.transform(data.scores)) == pytest.approx(roc_auc(data.y, data.scores), abs=1e-12)


def test_temperature_recovers_known_t():
    rng = np.random.default_rng(3)
    z = rng.normal(0, 3, 40000)
    y = (rng.random(z.size) < 1 / (1 + np.exp(-z / 2.0))).astype(int)
    data = C.ScoredSet([str(i) for i in range(z.size)], 1 / (1 + np.exp(-z)), y, split="val", manifest_sha256=SHA)
    assert C.fit(data, "temperature").params()["T"] == pytest.approx(2.0, rel=0.05)


def test_probability_calibrators_reject_out_of_range_scores():
    data = C.ScoredSet(["a", "b"], [1.5, -0.2], [1, 0], split="val", manifest_sha256=SHA)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        C.fit(data, "platt")


# --- threshold selection --------------------------------------------------------------------


def test_select_threshold_is_lowest_meeting_target():
    rng = np.random.default_rng(0)
    neg, pos = rng.uniform(0, 0.6, 1000), rng.uniform(0.4, 1, 1000)
    p = np.r_[neg, pos]
    y = np.r_[np.zeros(1000, int), np.ones(1000, int)]
    res = C.select_threshold(y, p, 0.05)
    assert not res["unachievable"] and not res["low_support"]
    assert res["achieved_fpr"] <= 0.05
    assert res["achieved_fpr"] == pytest.approx(np.mean(neg >= res["threshold"]))
    assert res["tpr"] == pytest.approx(np.mean(pos >= res["threshold"]))
    assert (res["n_neg"], res["n_pos"]) == (1000, 1000)
    lower = np.unique(p)[np.unique(p) < res["threshold"]].max()
    assert np.mean(neg >= lower) > 0.05


def test_low_support_and_unachievable():
    rng = np.random.default_rng(1)
    p = rng.random(100)
    y = rng.integers(0, 2, 100)
    res = C.select_threshold(y, p, 0.01)
    assert res["low_support"] and res["min_negatives"] == 1000
    assert not C.select_threshold(y, p, 0.01, min_negatives=10)["low_support"]

    flat = C.select_threshold([0, 1, 0, 1], [0.5] * 4, 0.05)
    assert flat["unachievable"] and flat["threshold"] is None and flat["reason"] == "no_threshold_meets_target"
    none = C.select_threshold([1, 1], [0.2, 0.9], 0.05)
    assert none["unachievable"] and none["reason"] == "no_negatives"


# --- calibration file -------------------------------------------------------------------------


@pytest.mark.parametrize("method", C.METHODS)
def test_round_trip_and_schema(tmp_path, method):
    data = _val_set()
    artifact, cal = C.build_calibration(
        data, channel="channel_b", score_name="ai_prob", method=method, seed=42,
        manifest_path="data/splits/split_v1.json",
    )
    path = tmp_path / "calibration.json"
    digest = C.save_calibration(artifact, path)
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest() == P.file_sha256(path)
    loaded = C.load_calibration(path)
    vec = np.linspace(0.001, 0.999, 500)
    np.testing.assert_allclose(loaded.apply(vec), cal.transform(vec), atol=1e-9, rtol=0)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["schema"] == "graphito.calibration/v1" and doc["method"] == method
    assert doc["manifest"] == {"path": "data/splits/split_v1.json", "sha256": SHA}
    assert doc["seed"] == 42 and doc["provenance"]["seed"] == 42 and "git_sha" in doc["provenance"]
    assert doc["fit_set"]["split"] == "val" and doc["fit_set"]["n"] == 2000
    assert doc["fit_set"]["n_pos"] + doc["fit_set"]["n_neg"] == 2000
    assert set(doc["thresholds"]) == {"fpr_0.05", "fpr_0.01"} and doc["primary"] == "fpr_0.05"
    assert doc["space"] == "calibrated"


def test_thresholds_live_in_calibrated_space():
    data = _val_set()
    artifact, cal = C.build_calibration(data, channel="channel_b", score_name="ai_prob", seed=0)
    expected = C.select_threshold(data.y, cal.transform(data.scores), 0.05)
    assert artifact["thresholds"]["fpr_0.05"]["threshold"] == expected["threshold"]


def test_writer_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "git_info", lambda cwd=None: {"git_sha": "f" * 40, "dirty": False})
    data = _val_set()
    paths = []
    for name in ("a.json", "b.json"):
        artifact, _ = C.build_calibration(data, channel="channel_b", score_name="ai_prob", seed=5)
        paths.append(tmp_path / name)
        C.save_calibration(artifact, paths[-1])
    raw = paths[0].read_bytes()
    assert raw == paths[1].read_bytes() and b"\r\n" not in raw


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="graphito.calibration/v2"),
        lambda d: d.pop("thresholds"),
        lambda d: d.update(method="beta"),
        lambda d: d["params"].pop(next(iter(d["params"]))),
        lambda d: d["fit_set"].update(split="test"),
    ],
)
def test_load_rejects_bad_files(tmp_path, mutate):
    artifact, _ = C.build_calibration(_val_set(200), channel="channel_b", score_name="ai_prob", seed=0)
    mutate(artifact)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError):
        C.load_calibration(path)


def _set_param(name, value):
    return lambda d: d["params"].__setitem__(name, value)


def _set_threshold_field(name, value):
    return lambda d: d["thresholds"]["fpr_0.05"].__setitem__(name, value)


@pytest.mark.parametrize(
    "method, mutate, message",
    [
        ("temperature", _set_param("T", 0.0), "T must be > 0"),
        ("temperature", _set_param("T", -2.0), "T must be > 0"),
        ("temperature", _set_param("T", "2.0"), "params.T"),
        ("temperature", _set_param("eps", float("nan")), "params.eps"),
        ("platt", _set_param("a", float("inf")), "params.a"),
        ("platt", _set_param("b", None), "params.b"),
        ("platt", _set_param("a", True), "params.a"),
        ("isotonic", _set_param("x", "0.1,0.9"), "params.x must be a list"),
        ("isotonic", _set_param("y", {"0": 0.5}), "params.y must be a list"),
        ("isotonic", _set_param("x", []), "non-empty"),
        ("isotonic", lambda d: d["params"]["x"].append(2.0), "equal length"),
        ("isotonic", lambda d: d["params"]["x"].reverse(), "strictly increasing"),
        ("isotonic", lambda d: d["params"]["y"].__setitem__(0, "low"), r"params.y\[0\]"),
        ("platt", _set_threshold_field("threshold", "0.5"), r"thresholds.fpr_0.05.threshold"),
        ("platt", _set_threshold_field("target_fpr", None), r"thresholds.fpr_0.05.target_fpr"),
        ("platt", lambda d: d.update(thresholds=[]), "thresholds must be a JSON object"),
        ("platt", lambda d: d.update(primary="fpr_0.5"), "primary 'fpr_0.5' is not among"),
    ],
)
def test_validate_rejects_bad_params_and_thresholds(method, mutate, message):
    artifact, _ = C.build_calibration(_val_set(200), channel="channel_b", score_name="ai_prob", method=method, seed=0)
    C.validate_calibration(artifact)
    mutate(artifact)
    with pytest.raises(C.CalibrationError, match=message):
        C.validate_calibration(artifact)


def test_save_calibration_failure_keeps_previous_file_and_no_temp(tmp_path, monkeypatch):
    artifact, _ = C.build_calibration(_val_set(200), channel="channel_b", score_name="ai_prob", seed=0)
    path = tmp_path / "calibration.json"
    path.write_bytes(b"previous\n")

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        C.save_calibration(artifact, path)
    monkeypatch.undo()
    assert path.read_bytes() == b"previous\n"
    assert [p.name for p in tmp_path.iterdir()] == ["calibration.json"]
    digest = C.save_calibration(artifact, path)
    assert digest == P.file_sha256(path) and [p.name for p in tmp_path.iterdir()] == ["calibration.json"]


def test_scored_set_normalizes_and_validates_inputs():
    data = C.ScoredSet(ids=[1, 2], scores=[0, 1], y=[0, 1], split="val", entry_splits=["val", "val"])
    assert data.ids == ("1", "2") and data.entry_splits == ("val", "val")
    assert data.scores.dtype == np.float64 and data.y.dtype == np.int64
    assert data.manifest_sha256 is None
    with pytest.raises(AttributeError):
        data.split = "test"
    with pytest.raises(ValueError, match="differ in length"):
        C.ScoredSet(["a"], [0.1, 0.2], [0, 1], "val")
    with pytest.raises(ValueError, match="one split per id"):
        C.ScoredSet(["a", "b"], [0.1, 0.2], [0, 1], "val", None, ["val"])
    with pytest.raises(ValueError, match="binary"):
        C.ScoredSet(["a", "b"], [0.1, 0.2], [0, 2], "val")


def test_build_requires_manifest_hash():
    data = C.ScoredSet(["a", "b"], [0.1, 0.9], [0, 1], split="val")
    with pytest.raises(ValueError, match="manifest"):
        C.build_calibration(data, channel="channel_b", score_name="ai_prob", seed=0)


def test_frozen_apply_changes_no_parameter(tmp_path, monkeypatch):
    artifact, _ = C.build_calibration(_val_set(), channel="channel_b", score_name="ai_prob", seed=0)
    path = tmp_path / "calibration.json"
    C.save_calibration(artifact, path)
    before = path.read_bytes()
    loaded = C.load_calibration(path)
    params = json.dumps(loaded.calibrator.params(), sort_keys=True)

    def refit(*_a, **_k):
        raise AssertionError("frozen calibration must not refit")

    monkeypatch.setattr(type(loaded.calibrator), "fit", refit)
    test_scores = np.random.default_rng(9).random(300)
    decisions = loaded.decide(test_scores)
    assert decisions.dtype == bool
    assert np.array_equal(decisions, loaded.apply(test_scores) >= artifact["thresholds"]["fpr_0.05"]["threshold"])
    assert json.dumps(loaded.calibrator.params(), sort_keys=True) == params
    assert path.read_bytes() == before


# --- provenance -------------------------------------------------------------------------------


def test_git_info_and_unknown_fallback(monkeypatch):
    info = P.git_info()
    assert info["git_sha"] == "unknown" or re.fullmatch(r"[0-9a-f]{40}", info["git_sha"])
    monkeypatch.setattr(P, "GIT", "git-executable-that-does-not-exist")
    assert P.git_info() == {"git_sha": "unknown", "dirty": "unknown"}


def test_file_sha256(tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(b"graphito" * 100000)
    assert P.file_sha256(path) == hashlib.sha256(b"graphito" * 100000).hexdigest()
