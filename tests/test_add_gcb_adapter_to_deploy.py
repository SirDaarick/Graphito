"""`scripts/add_gcb_adapter_to_deploy.py`: install the trained adapter into the verified deploy bundle."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("add_adapter", ROOT / "scripts" / "add_gcb_adapter_to_deploy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _adapter(tmp_path: Path, weights: bytes = b"weights") -> Path:
    d = tmp_path / "adapter_src"
    d.mkdir()
    (d / "adapter_model.safetensors").write_bytes(weights)
    (d / "adapter_config.json").write_text(json.dumps({"peft_type": "LORA", "r": 16, "lora_alpha": 32, "target_modules": ["query", "value"]}), encoding="utf-8")
    return d


def _bundle(tmp_path: Path) -> Path:
    deploy = tmp_path / "deploy"
    (deploy / "channel_a").mkdir(parents=True)
    other = b"calibration"
    (deploy / "channel_a" / "calibration.json").write_bytes(other)
    manifest = {"schema": "graphito.deploy-manifest/v1", "files": {"channel_a/calibration.json": _sha(other)},
                "gcb": {"model_name": "m", "fingerprint": "f" * 64}, "split_manifest_sha256": "a" * 64}
    (deploy / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return deploy


def test_install_copies_the_adapter_and_lists_it_with_hashes(tmp_path):
    deploy, adapter = _bundle(tmp_path), _adapter(tmp_path)
    mod.install(adapter, deploy, name="B_s1", source="runs/x")
    doc = json.loads((deploy / "manifest.json").read_text(encoding="utf-8"))
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        rel = f"gcb_adapter/{name}"
        assert (deploy / rel).read_bytes() == (adapter / name).read_bytes()
        assert doc["files"][rel] == _sha((adapter / name).read_bytes())
    section = doc["gcb"]["adapter"]
    assert section["name"] == "B_s1" and section["dir"] == "gcb_adapter" and section["rank"] == 16 and section["alpha"] == 32
    assert section["sha256"] == mod.adapter_sha256(adapter) and section["source"] == "runs/x"


def test_install_leaves_every_other_file_and_the_rest_of_the_manifest_untouched(tmp_path):
    deploy, adapter = _bundle(tmp_path), _adapter(tmp_path)
    before = json.loads((deploy / "manifest.json").read_text(encoding="utf-8"))
    mod.install(adapter, deploy, name="B_s1", source="s")
    after = json.loads((deploy / "manifest.json").read_text(encoding="utf-8"))
    assert after["files"]["channel_a/calibration.json"] == before["files"]["channel_a/calibration.json"]
    assert {k: v for k, v in after["gcb"].items() if k != "adapter"} == before["gcb"]
    assert {k: v for k, v in after.items() if k not in ("files", "gcb")} == {k: v for k, v in before.items() if k not in ("files", "gcb")}


def test_install_refuses_to_overwrite_an_installed_adapter_without_force(tmp_path):
    deploy, adapter = _bundle(tmp_path), _adapter(tmp_path)
    mod.install(adapter, deploy, name="B_s1", source="s")
    with pytest.raises(SystemExit):
        mod.install(_adapter(tmp_path / "other", b"w2") if (tmp_path / "other").mkdir() is None else adapter, deploy, name="B_s0", source="s")
    mod.install(adapter, deploy, name="B_s1", source="s", force=True)


def test_install_refuses_a_bundle_without_a_gcb_section(tmp_path):
    deploy, adapter = _bundle(tmp_path), _adapter(tmp_path)
    doc = json.loads((deploy / "manifest.json").read_text(encoding="utf-8"))
    del doc["gcb"]
    (deploy / "manifest.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.install(adapter, deploy, name="B_s1", source="s")


def test_install_refuses_a_directory_that_is_not_an_adapter(tmp_path):
    deploy = _bundle(tmp_path)
    (tmp_path / "empty").mkdir()
    with pytest.raises((FileNotFoundError, SystemExit)):
        mod.install(tmp_path / "empty", deploy, name="B_s1", source="s")
