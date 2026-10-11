"""Deploy manifest verification and settings (spec DA1.2, DA2.2, DA3.1-DA3.5; design D6, D7).

Uses the `fake_artifacts` fixture (tmp dir, real sha256, fake checkpoint bytes). The last test
checks the committed `models/deploy/` bundle and skips while it has not been built yet.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.infrastructure.artifacts import ArtifactError, load_bundle, load_bundle_from_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
COMMITTED_MANIFEST = REPO_ROOT / "models" / "deploy" / "manifest.json"


def _reason(exc_info) -> str:
    return exc_info.value.reason


def test_valid_bundle_exposes_thresholds_and_hashes(fake_artifacts):
    bundle = load_bundle(fake_artifacts.manifest)
    doc = fake_artifacts.read()
    assert bundle.channel_a.threshold_key == "fpr_0.05" and bundle.channel_a.threshold == 0.5
    assert bundle.channel_b.threshold_key == "fpr_0.01" and bundle.channel_b.threshold == 0.1715
    assert bundle.channel_a.calibration_sha256 == doc["files"]["channel_a/calibration.json"]
    assert bundle.channel_b.calibration_sha256 == doc["files"]["channel_b/calibration.json"]
    assert bundle.checkpoint_sha256 == doc["files"]["channel_b/best.pth"]
    assert bundle.checkpoint_path == fake_artifacts.root / "channel_b" / "best.pth"
    assert len(bundle.manifest_sha256) == 64
    assert bundle.label == "not validated against reference-derived plagiarism"


def test_isotonic_transform_matches_expected_values(fake_artifacts):
    bundle = load_bundle(fake_artifacts.manifest)
    got = bundle.channel_a.apply([0.0, 0.25, 0.5, 0.75, 1.0, 1.5])
    np.testing.assert_allclose(got, [0.0, 0.125, 0.25, 0.625, 1.0, 1.0], atol=1e-9, rtol=0)
    assert bundle.channel_a.flag(0.75) is True and bundle.channel_a.flag(0.5) is False


def test_sha_mismatch_fails_closed(fake_artifacts):
    fake_artifacts.write_file("channel_b/best.pth", b"tampered", update_manifest=False)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert _reason(exc) == "sha_mismatch"


def test_missing_file_fails_closed(fake_artifacts):
    (fake_artifacts.root / "channel_a" / "calibration.json").unlink()
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert _reason(exc) == "file_missing"


def test_missing_manifest_fails_closed(tmp_path):
    with pytest.raises(ArtifactError) as exc:
        load_bundle(tmp_path / "nope" / "manifest.json")
    assert _reason(exc) == "manifest_missing"


def test_unknown_schema_fails_closed(fake_artifacts):
    doc = fake_artifacts.read()
    doc["schema"] = "graphito.deploy-manifest/v2"
    fake_artifacts.write(doc)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert _reason(exc) == "unknown_schema"


@pytest.mark.parametrize("bad", ["../outside.json", "/abs/calibration.json", "C:/abs.json", "channel_a/../../x"])
def test_escaping_paths_fail_closed(fake_artifacts, bad):
    doc = fake_artifacts.read()
    doc["files"][bad] = "0" * 64
    fake_artifacts.write(doc)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert _reason(exc) == "path_escapes"


def test_null_threshold_for_configured_key_fails_closed(fake_artifacts):
    # Channel A's fpr_0.01 is unachievable (null) in the fake calibration.
    doc = fake_artifacts.read()
    doc["channel_a"]["threshold_key"] = "fpr_0.01"
    fake_artifacts.write(doc)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest, channel_a_key="fpr_0.01")
    assert _reason(exc) == "threshold_unachievable"


def test_configured_key_must_equal_manifest_key(fake_artifacts):
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest, channel_b_key="fpr_0.05")
    assert _reason(exc) == "threshold_key_mismatch"


def test_missing_key_in_calibration_fails_closed(fake_artifacts):
    doc = fake_artifacts.read()
    doc["channel_b"]["threshold_key"] = "fpr_0.001"
    fake_artifacts.write(doc)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest, channel_b_key="fpr_0.001")
    assert _reason(exc) == "threshold_key_missing"


def test_calibration_split_must_match_manifest(fake_artifacts):
    doc = fake_artifacts.read()
    doc["split_manifest_sha256"] = "d" * 64
    fake_artifacts.write(doc)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert _reason(exc) == "split_mismatch"


def test_invalid_calibration_fails_closed(fake_artifacts):
    cal = json.loads((fake_artifacts.root / "channel_a" / "calibration.json").read_text(encoding="utf-8"))
    cal["fit_set"]["split"] = "test"
    fake_artifacts.write_file("channel_a/calibration.json", json.dumps(cal).encode("utf-8"))
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert _reason(exc) == "calibration_invalid"


def test_configured_path_must_be_the_manifest_entry(fake_artifacts):
    other = fake_artifacts.root / "elsewhere.pth"
    other.write_bytes(b"x")
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest, charcnn_checkpoint=other)
    assert _reason(exc) == "not_in_manifest"


def test_error_message_has_no_partial_bundle(fake_artifacts):
    fake_artifacts.write_file("channel_b/best.pth", b"tampered", update_manifest=False)
    try:
        bundle = load_bundle(fake_artifacts.manifest)
    except ArtifactError:
        bundle = None
    assert bundle is None


def _settings(**overrides):
    return Settings(_env_file=None, **overrides)


def test_settings_defaults_keep_stub_mode():
    s = _settings()
    assert s.INFERENCE_MODE == "STUB"
    assert s.DEPLOY_MANIFEST == "models/deploy/manifest.json"
    assert s.CHANNEL_A_METHOD == "jaccard" and s.CHANNEL_A_THRESHOLD_KEY == "fpr_0.05"
    assert s.CHARCNN_THRESHOLD_KEY == "fpr_0.01" and s.GCB_INPUT_VERSION == "v2" and s.GCB_POOLING == "mean"
    assert s.GCB_SECONDARY_ENABLED is True and s.ALLOW_UNCALIBRATED is False
    assert s.APP_ENV == "development" and s.INFERENCE_WORKERS == 1


def test_allow_uncalibrated_refused_in_production():
    with pytest.raises(ValidationError, match="ALLOW_UNCALIBRATED"):
        _settings(APP_ENV="production", ALLOW_UNCALIBRATED=True)
    assert _settings(APP_ENV="development", ALLOW_UNCALIBRATED=True).ALLOW_UNCALIBRATED is True


def test_load_from_settings_resolves_paths(fake_artifacts):
    root = fake_artifacts.root
    s = _settings(
        DEPLOY_MANIFEST=str(fake_artifacts.manifest),
        CHANNEL_A_CALIBRATION=str(root / "channel_a" / "calibration.json"),
        CHARCNN_CALIBRATION=str(root / "channel_b" / "calibration.json"),
        CHARCNN_CHECKPOINT=str(root / "channel_b" / "best.pth"),
    )
    assert load_bundle_from_settings(s).channel_b.threshold == 0.1715
    with pytest.raises(ArtifactError) as exc:
        load_bundle_from_settings(s.model_copy(update={"CHANNEL_A_METHOD": "gcb"}))
    assert _reason(exc) == "method_mismatch"


def test_loading_needs_numpy_only(fake_artifacts):
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from app.infrastructure.artifacts import load_bundle;"
        f"b = load_bundle({str(fake_artifacts.manifest)!r});"
        "b.channel_a.apply([0.3]); b.channel_b.apply([0.3]);"
        "bad = [m for m in ('sklearn', 'torch', 'scipy') if m in sys.modules];"
        "assert not bad, bad"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr


@pytest.mark.skipif(not COMMITTED_MANIFEST.is_file(), reason="models/deploy/manifest.json not built yet (task 2.1)")
def test_committed_deploy_bundle_integrity():
    # DA1.2 / DA2.2: the committed bundle verifies (sha256, keys, non-escaping paths, val fit) and
    # both calibrations share the split manifest recorded in the deploy manifest.
    bundle = load_bundle(COMMITTED_MANIFEST)
    doc = json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8"))
    assert bundle.channel_a.threshold_key == "fpr_0.05" and bundle.channel_b.threshold_key == "fpr_0.01"
    assert bundle.channel_a.fit_split == "val" and bundle.channel_b.fit_split == "val"
    assert bundle.channel_a.split_manifest_sha256 == bundle.channel_b.split_manifest_sha256
    assert bundle.channel_a.split_manifest_sha256 == doc["split_manifest_sha256"]
    assert doc["build"]["limit_assignments"] is None
