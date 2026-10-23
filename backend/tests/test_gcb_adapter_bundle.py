"""The trained GraphCodeBERT adapter in the verified deploy bundle (`gcb.adapter`, loader side).

The adapter's files are listed with sha256 under `files` (so `verify_files` already refuses tampering) and its
identity `gcb.adapter.sha256` must equal what `models.graphcodebert.v2.adapter.adapter_sha256` computes. The
loader hashes with `hashlib` only: it must keep importing neither torch nor transformers.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.errors import ArtifactError
from app.infrastructure.artifacts import load_bundle
from app.infrastructure.artifacts.models_path import PROJECT_ROOT, ensure_on_path

BACKEND = Path(__file__).resolve().parents[1]
CONFIG = b'{"peft_type": "LORA", "r": 16, "lora_alpha": 32, "target_modules": ["query", "value"]}'
WEIGHTS = b"fake-lora-weights"


def identity(config: bytes, weights: bytes) -> str:
    digest = hashlib.sha256()
    for name, data in (("adapter_config.json", config), ("adapter_model.safetensors", weights)):
        digest.update(name.encode())
        digest.update(data)
    return digest.hexdigest()


def add_adapter(fake, config: bytes = CONFIG, weights: bytes = WEIGHTS, **section_overrides) -> dict:
    fake.write_file("gcb_adapter/adapter_config.json", config)
    fake.write_file("gcb_adapter/adapter_model.safetensors", weights)
    doc = fake.read()
    section = {"name": "B_s1", "dir": "gcb_adapter", "type": "lora", "sha256": identity(config, weights), "rank": 16, "alpha": 32,
               "target_modules": ["query", "value"], "source": "runs/contrastivo_codenet/f3/B_s1", **section_overrides}
    doc["gcb"]["adapter"] = section
    fake.write(doc)
    return section


def test_a_bundle_with_an_adapter_exposes_its_directory_name_and_identity(fake_artifacts):
    section = add_adapter(fake_artifacts)
    bundle = load_bundle(fake_artifacts.manifest)
    assert bundle.gcb_adapter_dir == fake_artifacts.root / "gcb_adapter"
    assert bundle.gcb_adapter_sha256 == section["sha256"] and bundle.gcb_adapter_name == "B_s1"
    assert bundle.summary()["gcb_adapter"] == {"name": "B_s1", "sha256": section["sha256"]}


def test_a_bundle_without_an_adapter_is_unchanged(fake_artifacts):
    bundle = load_bundle(fake_artifacts.manifest)
    assert bundle.gcb_adapter_dir is None and bundle.gcb_adapter_sha256 is None and bundle.gcb_adapter_name is None
    assert "gcb_adapter" not in bundle.summary()


def test_changed_weights_without_updating_the_manifest_are_refused(fake_artifacts):
    add_adapter(fake_artifacts)
    fake_artifacts.write_file("gcb_adapter/adapter_model.safetensors", b"tampered", update_manifest=False)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert exc.value.reason == "sha_mismatch"


def test_files_updated_but_identity_stale_is_refused(fake_artifacts):
    add_adapter(fake_artifacts)
    fake_artifacts.write_file("gcb_adapter/adapter_model.safetensors", b"retrained")  # files hash updated, identity not
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert exc.value.reason == "manifest_inconsistent"


def test_adapter_files_missing_from_the_manifest_listing_are_refused(fake_artifacts):
    add_adapter(fake_artifacts)
    doc = fake_artifacts.read()
    del doc["files"]["gcb_adapter/adapter_config.json"]
    fake_artifacts.write(doc)
    with pytest.raises(ArtifactError) as exc:
        load_bundle(fake_artifacts.manifest)
    assert exc.value.reason == "not_in_manifest"


@pytest.mark.parametrize("override", [{"sha256": "xyz"}, {"dir": ""}, {"dir": "../escape"}, {"name": 7}])
def test_malformed_adapter_sections_are_refused(fake_artifacts, override):
    add_adapter(fake_artifacts, **override)
    with pytest.raises(ArtifactError):
        load_bundle(fake_artifacts.manifest)


def test_the_loader_identity_equals_the_models_package_identity(tmp_path):
    ensure_on_path()
    from models.graphcodebert.v2.adapter import adapter_sha256

    d = tmp_path / "adapter"
    d.mkdir()
    (d / "adapter_config.json").write_bytes(CONFIG)
    (d / "adapter_model.safetensors").write_bytes(WEIGHTS)
    assert adapter_sha256(d) == identity(CONFIG, WEIGHTS)


def test_the_deployed_bundle_lists_the_frozen_f4_adapter():
    bundle = load_bundle(PROJECT_ROOT / "models" / "deploy" / "manifest.json")
    assert bundle.gcb_adapter_name == "B_s1"
    # the adapter frozen in F3/F4 (`odd/tasks/contrastivo-codenet-f3.md`, `f4_frozen.json`)
    assert bundle.gcb_adapter_sha256.startswith("b5842ab13eaa2718")
    assert bundle.gcb_adapter_dir.name == "gcb_adapter"


def test_loading_a_bundle_with_an_adapter_imports_neither_torch_nor_transformers(fake_artifacts):
    add_adapter(fake_artifacts)
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from app.infrastructure.artifacts import load_bundle;"
        f"b = load_bundle({str(fake_artifacts.manifest)!r}); assert b.gcb_adapter_dir is not None;"
        "bad = [m for m in ('sklearn', 'torch', 'scipy', 'transformers') if m in sys.modules];"
        "assert not bad, bad"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
