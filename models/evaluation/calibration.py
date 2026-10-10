"""Score calibration fitted on val only, FPR-targeted thresholds and `calibration.json`.

- `fit` refuses any data that is not entirely val (`ValueError`, not `assert`, so `python -O`
  cannot strip the check), per split tag, per entry and, when a manifest is given, per id.
- Thresholds live in calibrated space: consumers always apply the calibrator, then compare
  `p >= threshold`.
- scikit-learn (Platt, isotonic) and scipy (temperature) are imported lazily, inside `fit`.
"""

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from . import provenance
from .metrics import _labels

SCHEMA = "graphito.calibration/v1"
METHODS = ("temperature", "platt", "isotonic")
DEFAULT_METHOD = "platt"
DEFAULT_TARGETS = (0.05, 0.01)
EPS = 1e-7
# Default support rule (design): a target is low-support when n_neg * target < 10.
MIN_EXPECTED_FALSE_POSITIVES = 10

TOP_LEVEL_KEYS = (
    "schema", "channel", "score_name", "method", "params", "space", "thresholds", "primary",
    "fit_set", "manifest", "seed", "provenance",
)
PARAM_KEYS = {"temperature": ("T", "eps"), "platt": ("a", "b", "eps"), "isotonic": ("x", "y")}
THRESHOLD_KEYS = (
    "target_fpr", "threshold", "achieved_fpr", "tpr", "n_neg", "n_pos", "min_negatives",
    "low_support", "unachievable", "reason",
)


class CalibrationError(ValueError):
    """A calibration file is malformed or does not match `graphito.calibration/v1`."""


@dataclass(frozen=True, eq=False)
class ScoredSet:
    """Scores and binary labels for identified entries of one split.

    `split` is the tag the caller asserts; `entry_splits` (optional) is each entry's split as
    reported by the loader, checked one by one by `fit`.
    """

    ids: Tuple[str, ...]
    scores: np.ndarray
    y: np.ndarray
    split: str
    manifest_sha256: Optional[str] = None
    entry_splits: Optional[Tuple[str, ...]] = None

    def __init__(self, ids, scores, y, split, manifest_sha256=None, entry_splits=None):
        ids = tuple(str(i) for i in ids)
        scores = np.asarray(scores, dtype=np.float64)
        y = _labels(y)
        if not (len(ids) == scores.size == y.size) or scores.ndim != 1:
            raise ValueError(f"ids, scores and labels differ in length: {len(ids)}, {scores.shape}, {y.shape}")
        if entry_splits is not None:
            entry_splits = tuple(entry_splits)
            if len(entry_splits) != len(ids):
                raise ValueError("entry_splits must have one split per id")
        for name, value in (
            ("ids", ids), ("scores", scores), ("y", y), ("split", split),
            ("manifest_sha256", manifest_sha256), ("entry_splits", entry_splits),
        ):
            object.__setattr__(self, name, value)

    @classmethod
    def from_samples(cls, samples: Sequence, scores, y, *, manifest_sha256: Optional[str] = None) -> "ScoredSet":
        """Build from loader `Sample`s; `split` is their common split, else `mixed`."""
        splits = tuple(s.split for s in samples)
        split = splits[0] if splits and len(set(splits)) == 1 else "mixed"
        return cls([s.id for s in samples], scores, y, split, manifest_sha256, splits)

    def ids_labels_sha256(self) -> str:
        lines = sorted(f"{i}\t{int(label)}" for i, label in zip(self.ids, self.y))
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _require_val(data: ScoredSet, manifest=None) -> None:
    if data.entry_splits is not None:
        bad = [(i, s) for i, s in zip(data.ids, data.entry_splits) if s != "val"]
        if bad:
            raise ValueError(f"calibration fits on val only; entry {bad[0][0]!r} is {bad[0][1]!r} ({len(bad)} non-val)")
    if data.split != "val":
        raise ValueError(f"calibration fits on val only; got split {data.split!r}")
    if manifest is None:
        return
    if data.manifest_sha256 is not None and data.manifest_sha256 != manifest.sha256:
        raise ValueError(f"scored set manifest sha256 {data.manifest_sha256} != manifest {manifest.sha256}")
    for sample_id in data.ids:
        try:
            split = manifest.split_of(sample_id)
        except KeyError:
            raise ValueError(f"entry {sample_id!r} is not in the manifest") from None
        if split != "val":
            raise ValueError(f"calibration fits on val only; entry {sample_id!r} is {split!r} in the manifest")


# --- calibrators ----------------------------------------------------------------------------


def _check_probabilities(scores: np.ndarray) -> None:
    if scores.size and (np.isnan(scores).any() or scores.min() < 0.0 or scores.max() > 1.0):
        raise ValueError("temperature/Platt calibration needs scores in [0, 1]")


def _logit(scores, eps: float) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float64)
    _check_probabilities(scores)
    p = np.clip(scores, eps, 1.0 - eps)
    return np.log(p) - np.log1p(-p)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * z))


class Calibrator:
    """Monotone map from raw scores to calibrated probabilities."""

    method = ""

    def fit(self, scores, labels) -> "Calibrator":
        raise NotImplementedError

    def transform(self, scores) -> np.ndarray:
        raise NotImplementedError

    def params(self) -> Dict:
        raise NotImplementedError

    @classmethod
    def from_params(cls, params: Mapping) -> "Calibrator":
        raise NotImplementedError


class TemperatureCalibrator(Calibrator):
    """`sigmoid(logit(clip(s)) / T)`, T fitted by NLL (scipy bounded scalar search on log T)."""

    method = "temperature"

    def __init__(self, T: float = 1.0, eps: float = EPS):
        self.T, self.eps = float(T), float(eps)

    def fit(self, scores, labels):
        from scipy.optimize import minimize_scalar

        z, y = _logit(scores, self.eps), np.asarray(labels, dtype=np.float64)

        def nll(log_t):
            logits = z / math.exp(log_t)
            return float(np.sum(np.logaddexp(0.0, logits) - y * logits))

        res = minimize_scalar(nll, bounds=(-5.0, 5.0), method="bounded", options={"xatol": 1e-8})
        self.T = float(math.exp(res.x))
        return self

    def transform(self, scores):
        return _sigmoid(_logit(scores, self.eps) / self.T)

    def params(self):
        return {"T": self.T, "eps": self.eps}

    @classmethod
    def from_params(cls, params):
        return cls(T=params["T"], eps=params["eps"])


class PlattCalibrator(Calibrator):
    """`sigmoid(a * logit(clip(s)) + b)`, fitted by (effectively unpenalized) logistic regression."""

    method = "platt"

    def __init__(self, a: float = 1.0, b: float = 0.0, eps: float = EPS):
        self.a, self.b, self.eps = float(a), float(b), float(eps)

    def fit(self, scores, labels):
        from sklearn.linear_model import LogisticRegression

        z = _logit(scores, self.eps).reshape(-1, 1)
        model = LogisticRegression(C=1e10, max_iter=1000).fit(z, np.asarray(labels))
        self.a, self.b = float(model.coef_[0, 0]), float(model.intercept_[0])
        return self

    def transform(self, scores):
        return _sigmoid(self.a * _logit(scores, self.eps) + self.b)

    def params(self):
        return {"a": self.a, "b": self.b, "eps": self.eps}

    @classmethod
    def from_params(cls, params):
        return cls(a=params["a"], b=params["b"], eps=params["eps"])


class IsotonicCalibrator(Calibrator):
    """Non-decreasing step-linear map (scikit-learn PAV); stores its knots, clips outside them.

    Ranking is preserved weakly: plateaus may tie scores, but never invert them."""

    method = "isotonic"

    def __init__(self, x: Sequence[float] = (0.0, 1.0), y: Sequence[float] = (0.0, 1.0)):
        self.x = np.asarray(x, dtype=np.float64)
        self.y = np.asarray(y, dtype=np.float64)

    def fit(self, scores, labels):
        from sklearn.isotonic import IsotonicRegression

        model = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
        model.fit(np.asarray(scores, dtype=np.float64), np.asarray(labels, dtype=np.float64))
        self.x = np.asarray(model.X_thresholds_, dtype=np.float64)
        self.y = np.asarray(model.y_thresholds_, dtype=np.float64)
        return self

    def transform(self, scores):
        return np.interp(np.asarray(scores, dtype=np.float64), self.x, self.y)

    def params(self):
        return {"x": [float(v) for v in self.x], "y": [float(v) for v in self.y]}

    @classmethod
    def from_params(cls, params):
        if len(params["x"]) != len(params["y"]) or not params["x"]:
            raise CalibrationError("isotonic knots x and y must be non-empty and of equal length")
        return cls(x=params["x"], y=params["y"])


_CALIBRATORS = {c.method: c for c in (TemperatureCalibrator, PlattCalibrator, IsotonicCalibrator)}


def make_calibrator(method: str) -> Calibrator:
    if method not in _CALIBRATORS:
        raise ValueError(f"unknown calibration method {method!r} (want one of {METHODS})")
    return _CALIBRATORS[method]()


def fit(data: ScoredSet, method: str = DEFAULT_METHOD, *, manifest=None) -> Calibrator:
    """Fit a calibrator on val data only; raises `ValueError` on any non-val entry."""
    _require_val(data, manifest)
    return make_calibrator(method).fit(data.scores, data.y)


# --- threshold selection --------------------------------------------------------------------


def threshold_key(target_fpr: float) -> str:
    return f"fpr_{target_fpr:g}"


def select_threshold(y, p, target_fpr: float, *, min_negatives: Optional[int] = None) -> Dict:
    """Lowest observed score `t` whose FPR (`p >= t`) on these data is <= `target_fpr`.

    Records achieved FPR, TPR and support. `low_support` when the negatives are fewer than
    `min_negatives` (default `ceil(10 / target_fpr)`, i.e. fewer than 10 expected false
    positives). When no observed score meets the target (or there are no negatives) the
    result is `unachievable` with `threshold` None, never an arbitrary value.
    """
    y = _labels(y)
    p = np.asarray(p, dtype=np.float64)
    if p.shape != y.shape:
        raise ValueError(f"labels and scores differ in length: {y.shape} vs {p.shape}")
    if not 0.0 < target_fpr < 1.0:
        raise ValueError(f"target FPR must be in (0, 1), got {target_fpr}")
    neg, pos = np.sort(p[y == 0]), p[y == 1]
    if min_negatives is None:
        min_negatives = math.ceil(MIN_EXPECTED_FALSE_POSITIVES / target_fpr - 1e-9)
    result = {
        "target_fpr": float(target_fpr),
        "threshold": None,
        "achieved_fpr": None,
        "tpr": None,
        "n_neg": int(neg.size),
        "n_pos": int(pos.size),
        "min_negatives": int(min_negatives),
        "low_support": bool(neg.size < min_negatives),
        "unachievable": False,
        "reason": None,
    }
    if neg.size == 0:
        return {**result, "unachievable": True, "reason": "no_negatives"}
    candidates = np.unique(p)
    fpr = (neg.size - np.searchsorted(neg, candidates, side="left")) / neg.size
    meeting = np.flatnonzero(fpr <= target_fpr)
    if meeting.size == 0:
        return {**result, "unachievable": True, "reason": "no_threshold_meets_target"}
    t = float(candidates[meeting[0]])
    return {
        **result,
        "threshold": t,
        "achieved_fpr": float(fpr[meeting[0]]),
        "tpr": float(np.mean(pos >= t)) if pos.size else None,
    }


# --- calibration file -----------------------------------------------------------------------


def build_calibration(
    data: ScoredSet,
    *,
    channel: str,
    score_name: str,
    seed: int,
    method: str = DEFAULT_METHOD,
    targets: Sequence[float] = DEFAULT_TARGETS,
    manifest=None,
    manifest_path: Optional[Union[str, Path]] = None,
    min_negatives: Optional[int] = None,
) -> Tuple[Dict, Calibrator]:
    """Fit on val, select thresholds in calibrated space and return `(artifact, calibrator)`.

    The artifact is the `graphito.calibration/v1` document; nothing is written here."""
    manifest_sha256 = data.manifest_sha256 or getattr(manifest, "sha256", None)
    calibrator = fit(data, method, manifest=manifest)
    if not manifest_sha256:
        raise ValueError("calibration needs the split manifest sha256 (ScoredSet.manifest_sha256 or manifest)")
    if not targets:
        raise ValueError("at least one FPR target is required")
    calibrated = calibrator.transform(data.scores)
    thresholds = {
        threshold_key(t): select_threshold(data.y, calibrated, t, min_negatives=min_negatives) for t in targets
    }
    if manifest_path is None and manifest is not None:
        manifest_path = getattr(manifest, "path", None)
    git = provenance.git_info()
    artifact = {
        "schema": SCHEMA,
        "channel": channel,
        "score_name": score_name,
        "method": method,
        "params": calibrator.params(),
        "space": "calibrated",
        "thresholds": thresholds,
        "primary": threshold_key(targets[0]),
        "fit_set": {
            "split": "val",
            "n": int(data.y.size),
            "n_pos": int(data.y.sum()),
            "n_neg": int(data.y.size - data.y.sum()),
            "ids_labels_sha256": data.ids_labels_sha256(),
        },
        "manifest": {
            "path": Path(manifest_path).as_posix() if manifest_path is not None else None,
            "sha256": manifest_sha256,
        },
        "seed": seed,
        "provenance": {"git_sha": git["git_sha"], "dirty": git["dirty"], "seed": seed},
    }
    return artifact, calibrator


def _require_keys(doc: Mapping, keys, where: str) -> None:
    if not isinstance(doc, Mapping):
        raise CalibrationError(f"{where} must be a JSON object")
    missing = [k for k in keys if k not in doc]
    if missing:
        raise CalibrationError(f"{where} lacks keys {missing}")


def validate_calibration(artifact: Mapping) -> None:
    """Raise `CalibrationError` unless `artifact` matches `graphito.calibration/v1`."""
    _require_keys(artifact, ("schema",), "calibration")
    if artifact["schema"] != SCHEMA:
        raise CalibrationError(f"unknown calibration schema {artifact['schema']!r} (want {SCHEMA})")
    _require_keys(artifact, TOP_LEVEL_KEYS, "calibration")
    if artifact["method"] not in METHODS:
        raise CalibrationError(f"unknown calibration method {artifact['method']!r}")
    _require_keys(artifact["params"], PARAM_KEYS[artifact["method"]], "params")
    if artifact["space"] != "calibrated":
        raise CalibrationError(f"thresholds must be in calibrated space, got {artifact['space']!r}")
    if not isinstance(artifact["thresholds"], Mapping) or artifact["primary"] not in artifact["thresholds"]:
        raise CalibrationError(f"primary {artifact['primary']!r} is not among the thresholds")
    for key, entry in artifact["thresholds"].items():
        _require_keys(entry, THRESHOLD_KEYS, f"thresholds.{key}")
    _require_keys(artifact["fit_set"], ("split", "n", "n_pos", "n_neg", "ids_labels_sha256"), "fit_set")
    if artifact["fit_set"]["split"] != "val":
        raise CalibrationError(f"calibration must be fitted on val, got {artifact['fit_set']['split']!r}")
    _require_keys(artifact["manifest"], ("path", "sha256"), "manifest")
    if not artifact["manifest"]["sha256"]:
        raise CalibrationError("calibration lacks the split manifest sha256")
    _require_keys(artifact["provenance"], ("git_sha", "dirty", "seed"), "provenance")


def calibrator_from_artifact(artifact: Mapping) -> Calibrator:
    validate_calibration(artifact)
    return _CALIBRATORS[artifact["method"]].from_params(artifact["params"])


def save_calibration(artifact: Mapping, path: Union[str, Path]) -> str:
    """Validate and write deterministically (sorted keys, LF, no wall clock); return sha256.

    The file is written to a sibling temp file and moved into place, so a failed write
    never leaves a partial `calibration.json`."""
    validate_calibration(artifact)
    raw = (json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class LoadedCalibration:
    """A frozen calibration: applying it never refits or changes a parameter."""

    path: Path
    sha256: str
    artifact: Dict
    calibrator: Calibrator

    def apply(self, scores) -> np.ndarray:
        return self.calibrator.transform(scores)

    def threshold(self, key: Optional[str] = None) -> Dict:
        return self.artifact["thresholds"][key or self.artifact["primary"]]

    def decide(self, scores, key: Optional[str] = None) -> np.ndarray:
        """Boolean decisions `calibrated >= threshold` at `key` (primary by default)."""
        entry = self.threshold(key)
        if entry["unachievable"] or entry["threshold"] is None:
            raise ValueError(f"threshold {key or self.artifact['primary']} is unachievable ({entry['reason']})")
        return self.apply(scores) >= entry["threshold"]


def load_calibration(path: Union[str, Path]) -> LoadedCalibration:
    """Read, schema-validate and rebuild a calibration file."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"{path}: not valid UTF-8 JSON ({exc})") from None
    calibrator = calibrator_from_artifact(artifact)
    return LoadedCalibration(path, hashlib.sha256(raw).hexdigest(), artifact, calibrator)
