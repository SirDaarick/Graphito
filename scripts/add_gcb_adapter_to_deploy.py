"""Install the trained GraphCodeBERT LoRA adapter into the verified deploy bundle `models/deploy/`.

Copies `adapter_config.json` and `adapter_model.safetensors` to `models/deploy/gcb_adapter/`, lists both with
their sha256 under `files` of `manifest.json` (the backend loader refuses any file whose hash it does not list)
and describes the adapter in `gcb.adapter`. Nothing else in the manifest changes: the Channel A/B calibrations,
the CharCNN checkpoint and every other field keep their bytes, so this does not need the long
`build_deploy_artifacts.py` run. The adapter identity `gcb.adapter.sha256` is the one
`models.graphcodebert.v2.adapter.adapter_sha256` computes; the engine folds it into the Chroma collection name.

    python scripts/add_gcb_adapter_to_deploy.py \\
        --adapter C:\\Users\\edani\\datasets\\codenet\\f3\\B_s1\\adapter --name B_s1 \\
        --source runs/contrastivo_codenet/f3/B_s1
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.graphcodebert.v2.adapter import adapter_sha256  # noqa: E402

DEPLOY_DIR = ROOT / "models" / "deploy"
ADAPTER_SUBDIR = "gcb_adapter"
ADAPTER_FILES = ("adapter_config.json", "adapter_model.safetensors")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: Dict[str, Any]) -> bytes:
    # same formatting as build_deploy_artifacts.py, so a later rebuild diffs cleanly
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def install(adapter_dir: Path, deploy_dir: Path, *, name: str, source: str, force: bool = False) -> Dict[str, Any]:
    """Copy the adapter into `deploy_dir` and update its manifest. Returns the `gcb.adapter` section."""
    adapter_dir, deploy_dir = Path(adapter_dir), Path(deploy_dir)
    identity = adapter_sha256(adapter_dir)  # FileNotFoundError when it is not an adapter directory
    manifest_path = deploy_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"{manifest_path} not found: build the deploy bundle first")
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(doc.get("gcb"), dict):
        raise SystemExit("the deploy manifest has no gcb section: the adapter belongs to the GraphCodeBERT signal")
    if "adapter" in doc["gcb"] and not force:
        raise SystemExit(f"an adapter ({doc['gcb']['adapter'].get('name')!r}) is already installed; use --force to replace it")
    cfg = json.loads((adapter_dir / "adapter_config.json").read_text(encoding="utf-8"))
    target = deploy_dir / ADAPTER_SUBDIR
    target.mkdir(parents=True, exist_ok=True)
    files = dict(doc["files"])
    for fname in ADAPTER_FILES:
        shutil.copyfile(adapter_dir / fname, target / fname)
        files[f"{ADAPTER_SUBDIR}/{fname}"] = _sha((target / fname).read_bytes())
    section = {
        "name": name,
        "dir": ADAPTER_SUBDIR,
        "type": "lora",
        "sha256": identity,
        "rank": cfg["r"],
        "alpha": cfg["lora_alpha"],
        "target_modules": sorted(cfg["target_modules"]),
        "source": source,
    }
    doc["files"] = files
    doc["gcb"] = {**doc["gcb"], "adapter": section}
    manifest_path.write_bytes(_json_bytes(doc))
    return section


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--adapter", type=Path, required=True, help="PEFT adapter directory (adapter_config.json + adapter_model.safetensors)")
    ap.add_argument("--name", required=True, help="short name recorded in the manifest, e.g. B_s1")
    ap.add_argument("--source", required=True, help="where the adapter's evidence lives, e.g. runs/contrastivo_codenet/f3/B_s1")
    ap.add_argument("--deploy-dir", type=Path, default=DEPLOY_DIR)
    ap.add_argument("--force", action="store_true", help="replace an adapter that is already installed")
    args = ap.parse_args(argv)
    section = install(args.adapter, args.deploy_dir, name=args.name, source=args.source, force=args.force)
    print(json.dumps(section, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
