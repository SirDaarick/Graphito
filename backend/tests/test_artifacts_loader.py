"""Calibration ports over the deploy bundle and the STUB defaults (spec DA3.3, DA3.4, AS5.2).

The fail-closed loader cases (sha mismatch, missing file, unknown schema, missing key, null
threshold, key mismatch, settings validators) live in `test_deploy_artifacts.py`.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.ports.calibration_port import CalibratedChannel, CalibrationPort
from app.infrastructure.artifacts import load_bundle
from app.infrastructure.artifacts.calibration import BundleCalibration
from app.infrastructure.artifacts.models_path import PROJECT_ROOT, ensure_on_path
from app.infrastructure.artifacts.stub_artifacts import STUB_THRESHOLD_KEY, StubCalibration

BACKEND = Path(__file__).resolve().parents[1]


def test_bundle_calibration_exposes_thresholds_and_hashes(fake_artifacts):
    bundle = load_bundle(fake_artifacts.manifest)
    port = BundleCalibration(bundle)
    doc = fake_artifacts.read()
    assert isinstance(port, CalibrationPort) and port.engine == "real"
    a, b = port.channel("a"), port.channel("b")
    assert isinstance(a, CalibratedChannel) and isinstance(b, CalibratedChannel)
    assert (a.threshold_key, a.threshold) == ("fpr_0.05", 0.5)
    assert (b.threshold_key, b.threshold) == ("fpr_0.01", 0.1715)
    assert a.calibration_sha256 == doc["files"]["channel_a/calibration.json"]
    assert b.calibration_sha256 == doc["files"]["channel_b/calibration.json"]
    assert port.checkpoint_sha256 == doc["files"]["channel_b/best.pth"]
    assert port.manifest_sha256 == bundle.manifest_sha256
    assert port.label == "not validated against reference-derived plagiarism"


def test_scalar_calibrate_matches_isotonic_and_platt(fake_artifacts):
    port = BundleCalibration(load_bundle(fake_artifacts.manifest))
    # Isotonic identity-like fit: x [0, .5, 1] -> y [0, .25, 1]; Platt a=1, b=0 -> sigmoid.
    assert port.channel("a").calibrate(0.75) == pytest.approx(0.625, abs=1e-9)
    assert isinstance(port.channel("a").calibrate(0.75), float)
    # Platt a=1, b=0 is the identity on probabilities: sigmoid(logit(p)).
    assert port.channel("b").calibrate(0.5) == pytest.approx(0.5, abs=1e-9)
    assert port.channel("b").calibrate(0.2) == pytest.approx(0.2, abs=1e-9)


def test_unknown_channel_name_is_refused(fake_artifacts):
    port = BundleCalibration(load_bundle(fake_artifacts.manifest))
    with pytest.raises(KeyError):
        port.channel("c")


def test_stub_calibration_has_fixed_defaults_and_no_hashes():
    port = StubCalibration()
    assert port.engine == "stub"
    a, b = port.channel("a"), port.channel("b")
    assert a.threshold_key == b.threshold_key == STUB_THRESHOLD_KEY
    assert a.calibration_sha256 is None and b.calibration_sha256 is None
    assert port.checkpoint_sha256 is None and port.manifest_sha256 is None
    assert a.calibrate(0.3) == 0.3 and b.calibrate(0.7) == 0.7
    assert 0.0 < a.threshold < 1.0 and 0.0 < b.threshold < 1.0


def test_ensure_on_path_adds_the_project_root_once(monkeypatch):
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(PROJECT_ROOT)])
    ensure_on_path()
    ensure_on_path()
    assert sys.path.count(str(PROJECT_ROOT)) == 1
    assert (PROJECT_ROOT / "models").is_dir()


def test_calibration_adapters_import_neither_sklearn_nor_torch(fake_artifacts):
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from app.infrastructure.artifacts import load_bundle;"
        "from app.infrastructure.artifacts.calibration import BundleCalibration;"
        "from app.infrastructure.artifacts.stub_artifacts import StubCalibration;"
        f"p = BundleCalibration(load_bundle({str(fake_artifacts.manifest)!r}));"
        "p.channel('a').calibrate(0.3); p.channel('b').calibrate(0.3); StubCalibration().channel('b').calibrate(1.0);"
        "bad = [m for m in ('sklearn', 'torch', 'scipy') if m in sys.modules];"
        "assert not bad, bad"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
