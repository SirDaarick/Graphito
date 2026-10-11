"""Build the backend deploy artifacts under `models/deploy/` (SDD-4 design D1-D3, spec DA1-DA2).

    python scripts/build_deploy_artifacts.py \
        --charcnn-run runs/char_cnn/20261011-015734 \
        --gcb-run runs/graphcodebert/20261011-082155

What it writes (and nothing else; this script is the only writer of `models/deploy/`):

- `channel_b/best.pth`, `channel_b/calibration.json`: verbatim copies of the CharCNN v2 run's
  checkpoint and Platt calibration (their sha256 must match the run's `config.json`).
- `channel_a/calibration.json`: an isotonic `graphito.calibration/v1` calibration of the Channel A
  lexical score (5-token shingle Jaccard), fitted on the split_v1 **val** plagiarism pairs only,
  scored per assignment block exactly as the SDD-3 GraphCodeBERT evaluation scores its `jaccard`
  baseline (`EvalPairs`, `SetSimilarity`, `jaccard_set`). Targets FPR 0.05 and 0.01; the build
  refuses (exit 1) when `fpr_0.05` is unachievable.
- `manifest.json` (`graphito.deploy-manifest/v1`): sha256 of every file, source run ids, threshold
  keys and values, raw-space reference thresholds, git sha/dirty and package versions.

Safety: every input is checked before anything is written; existing files with different bytes
are refused unless `--force`; each file is written atomically and the manifest last, so a failed
build never leaves a manifest that points at the wrong bytes. `models/char_cnn/best_model.pth`
(the legacy checkpoint) is never read or written. `--limit-assignments N` (debug) scores only the
first N val assignments and is refused for the default output directory unless `--dry-run`.

Exit codes: 0 built (or dry run), 1 refused (nothing written), 2 usage error.

The artifacts are NOT validated against reference-derived plagiarism; the manifest carries that
label and the backend shows it.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.evaluation.calibration import (  # noqa: E402
    CalibrationError,
    ScoredSet,
    build_calibration,
    load_calibration,
    validate_calibration,
)
from models.evaluation.dedup import SHINGLE_K  # noqa: E402
from models.evaluation.manifest import DEFAULT_MANIFEST, ManifestError, load_manifest  # noqa: E402
from models.evaluation.provenance import atomic_write_bytes, git_info, package_versions  # noqa: E402

SCHEMA = "graphito.deploy-manifest/v1"
DEFAULT_OUT = ROOT / "models" / "deploy"
PROTECTED_CHECKPOINT = ROOT / "models" / "char_cnn" / "best_model.pth"
LABEL = "not validated against reference-derived plagiarism"
CHANNEL_A_KEY = "fpr_0.05"
CHANNEL_B_KEY = "fpr_0.01"
CHANNEL_A_TARGETS = (0.05, 0.01)
GCB_POOLING = "mean"
GCB_FINGERPRINT_FIELDS = (
    "model_name", "model_revision", "input_version", "walker_version", "pooling", "use_dfg",
    "code_length", "data_flow_length", "max_windows", "dtype",
)
VERSION_PACKAGES = ("numpy", "scipy", "scikit-learn")
REFUSED_EXIT = 1

A_CALIBRATION = "channel_a/calibration.json"
B_CHECKPOINT = "channel_b/best.pth"
B_CALIBRATION = "channel_b/calibration.json"
MANIFEST_NAME = "manifest.json"


class BuildRefused(Exception):
    """A pre-write check failed; nothing has been written."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: Mapping) -> bytes:
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _read_json(path: Path) -> Dict:
    if not path.is_file():
        raise BuildRefused(f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildRefused(f"{path}: not valid JSON ({exc})") from None


def _rel(path: Path) -> str:
    """Repository-relative POSIX path when possible (no user paths in committed files)."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def check_out_dir(out: Path) -> None:
    """Refuse an output directory that is, or contains, the legacy checkpoint's directory."""
    out = Path(out).resolve()
    protected = PROTECTED_CHECKPOINT.resolve()
    if out == protected or out in protected.parents:
        raise BuildRefused(f"refusing to write under {out}: it contains {_rel(protected)}")


# --- inputs ---------------------------------------------------------------------------------------


def read_charcnn_run(run_dir: Path) -> Dict[str, Any]:
    """Checkpoint and calibration bytes of a CharCNN v2 run, cross-checked with its config."""
    run_dir = Path(run_dir)
    best, cal = run_dir / "best.pth", run_dir / "calibration.json"
    for p in (best, cal):
        if not p.is_file():
            raise BuildRefused(f"CharCNN run lacks {p.name}: {run_dir}")
        if p.resolve() == PROTECTED_CHECKPOINT.resolve():
            raise BuildRefused("the legacy checkpoint is not a CharCNN v2 run artifact")
    config = _read_json(run_dir / "config.json")
    best_bytes, cal_bytes = best.read_bytes(), cal.read_bytes()
    if config.get("best_sha256") != _sha(best_bytes):
        raise BuildRefused(f"{best}: sha256 differs from the run's config.json best_sha256")
    if config.get("calibration_sha256") not in (None, _sha(cal_bytes)):
        raise BuildRefused(f"{cal}: sha256 differs from the run's config.json calibration_sha256")
    try:
        loaded = load_calibration(cal)
    except CalibrationError as exc:
        raise BuildRefused(f"{cal}: {exc}") from None
    entry = loaded.artifact["thresholds"].get(CHANNEL_B_KEY)
    if entry is None or entry["threshold"] is None:
        raise BuildRefused(f"{cal}: threshold {CHANNEL_B_KEY} is missing or unachievable")
    inner = config.get("config") or {}
    return {
        "run_id": config.get("run_id") or f"char_cnn/{run_dir.name}",
        "best": best_bytes,
        "calibration": cal_bytes,
        "artifact": loaded.artifact,
        "threshold": entry,
        "arch_version": inner.get("arch_version"),
        "preproc_version": inner.get("preproc_version"),
    }


def read_gcb_run(run_dir: Path) -> Dict[str, Any]:
    """The SDD-3 GraphCodeBERT run: identity, raw Jaccard val thresholds and val selection stats."""
    run_dir = Path(run_dir)
    config = _read_json(run_dir / "config.json")
    thresholds = _read_json(run_dir / "thresholds_val.json")
    selection = _read_json(run_dir / "selection.json")
    jaccard = ((thresholds.get("methods") or {}).get("jaccard") or {}).get("thresholds") or {}
    inner = config.get("config") or {}
    return {
        "run_id": config.get("run_id") or f"graphcodebert/{run_dir.name}",
        "manifest_sha256": config.get("manifest_sha256"),
        "model_name": inner.get("model_name"),
        "model_revision": inner.get("model_revision"),
        "gcb_v2": inner.get("gcb_v2") or {},
        "raw_jaccard": {k: (v or {}).get("threshold") for k, v in jaccard.items()},
        "val_n_pairs": selection.get("n_pairs"),
        "val_files_sha256": selection.get("files_sha256"),
    }


def score_val_pairs(manifest, root: Path, limit_assignments: Optional[int] = None) -> Tuple[ScoredSet, Dict]:
    """Channel A raw scores of the val plagiarism pairs, exactly as SDD-3 scores `jaccard`.

    Imported lazily: the GraphCodeBERT evaluation module pulls in torch/transformers."""
    from models.graphcodebert.v2.baselines import SetSimilarity, jaccard_set
    from models.graphcodebert.v2.evaluate import Refused, load_files
    from models.graphcodebert.v2.pairs import EvalPairs, score_pairs

    val = EvalPairs.from_manifest(manifest, "val", limit_assignments=limit_assignments)
    try:
        files = load_files(Path(root), val.samples)
    except Refused as exc:
        raise BuildRefused(str(exc)) from None
    sets = SetSimilarity([jaccard_set(files[i].text) for i in val.pairs.ids])
    scores = score_pairs(sets, val, views=("all",)).scores
    ids = val.pairs.ids
    data = ScoredSet(
        [f"{ids[a]}|{ids[b]}" for a, b in zip(val.pairs.a, val.pairs.b)],
        scores, val.pairs.label.astype(np.int64), "val", manifest_sha256=manifest.sha256,
    )
    info = {
        "n_files": len(ids),
        "n_pairs": int(val.pairs.a.size),
        "files_sha256": hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest(),
    }
    return data, info


def fit_channel_a(data: ScoredSet, *, seed: int, manifest_path: str) -> Tuple[Dict, Dict]:
    """Isotonic calibration on val; refuses when `fpr_0.05` is unachievable (design D3)."""
    artifact, calibrator = build_calibration(
        data, channel="jaccard", score_name="jaccard_shingle5", seed=seed, method="isotonic",
        targets=CHANNEL_A_TARGETS, manifest_path=manifest_path,
    )
    entry = artifact["thresholds"][CHANNEL_A_KEY]
    if entry["unachievable"] or entry["threshold"] is None:
        raise BuildRefused(f"Channel A {CHANNEL_A_KEY} is unachievable on val ({entry['reason']})")
    calibrated = calibrator.transform(data.scores)
    flagged = data.scores[calibrated >= entry["threshold"]]
    raw_equivalent = float(flagged.min()) if flagged.size else None
    return artifact, {"raw_threshold_equivalent": raw_equivalent}


def gcb_fingerprint(fields: Mapping[str, Any]) -> str:
    """sha256 of the canonical JSON of the embedding pipeline fields (design D12)."""
    canonical = json.dumps({k: fields.get(k) for k in GCB_FINGERPRINT_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- build ----------------------------------------------------------------------------------------


def build(args) -> Tuple[Dict[str, bytes], Dict]:
    """All output bytes (relative path -> bytes, manifest included) after every check."""
    try:
        manifest = load_manifest(args.manifest)
    except (ManifestError, OSError) as exc:
        raise BuildRefused(f"split manifest: {exc}") from None
    charcnn = read_charcnn_run(Path(args.charcnn_run))
    gcb = read_gcb_run(Path(args.gcb_run))

    split_sha = manifest.sha256
    cnn_sha = charcnn["artifact"]["manifest"]["sha256"]
    if cnn_sha != split_sha:
        raise BuildRefused(f"CharCNN calibration split manifest {cnn_sha} != {split_sha} (DA2.2)")
    if gcb["manifest_sha256"] != split_sha:
        raise BuildRefused(f"GraphCodeBERT run split manifest {gcb['manifest_sha256']} != {split_sha}")

    data, val_info = score_val_pairs(manifest, Path(args.root), args.limit_assignments)
    if args.limit_assignments is None:
        if (gcb["val_n_pairs"], gcb["val_files_sha256"]) != (val_info["n_pairs"], val_info["files_sha256"]):
            raise BuildRefused("val pairs differ from the GraphCodeBERT run's selection.json (different corpus?)")
    a_artifact, a_extra = fit_channel_a(data, seed=args.seed, manifest_path=_rel(Path(args.manifest)))
    validate_calibration(a_artifact)
    a_bytes = _json_bytes(a_artifact)
    a_entry = a_artifact["thresholds"][CHANNEL_A_KEY]

    files = {A_CALIBRATION: a_bytes, B_CHECKPOINT: charcnn["best"], B_CALIBRATION: charcnn["calibration"]}
    gcb_fields = {
        "model_name": gcb["model_name"], "model_revision": gcb["model_revision"], "pooling": GCB_POOLING,
        **{k: gcb["gcb_v2"].get(k) for k in GCB_FINGERPRINT_FIELDS if k not in ("model_name", "model_revision", "pooling")},
    }
    git = git_info()
    doc = {
        "schema": SCHEMA,
        "build": {
            "script": "scripts/build_deploy_artifacts.py",
            "git_sha": git["git_sha"],
            "dirty": git["dirty"],
            "seed": args.seed,
            "limit_assignments": args.limit_assignments,
            "versions": package_versions(VERSION_PACKAGES),
        },
        "split_manifest_sha256": split_sha,
        "label": LABEL,
        "files": {rel: _sha(content) for rel, content in sorted(files.items())},
        "channel_a": {
            "method": "jaccard",
            "shingle_k": SHINGLE_K,
            "calibration": A_CALIBRATION,
            "calibration_method": "isotonic",
            "threshold_key": CHANNEL_A_KEY,
            "threshold": a_entry["threshold"],
            "achieved_fpr": a_entry["achieved_fpr"],
            "tpr": a_entry["tpr"],
            "fit_set": {"split": "val", **val_info, "n_pos": int(data.y.sum())},
            "raw_threshold_equivalent": a_extra["raw_threshold_equivalent"],
            "raw_val_threshold_ref": gcb["raw_jaccard"].get(CHANNEL_A_KEY),
            "source_run": gcb["run_id"],
        },
        "channel_b": {
            "method": "charcnn_v2",
            "checkpoint": B_CHECKPOINT,
            "calibration": B_CALIBRATION,
            "calibration_method": charcnn["artifact"]["method"],
            "threshold_key": CHANNEL_B_KEY,
            "threshold": charcnn["threshold"]["threshold"],
            "achieved_fpr": charcnn["threshold"]["achieved_fpr"],
            "tpr": charcnn["threshold"]["tpr"],
            "arch_version": charcnn["arch_version"],
            "preproc_version": charcnn["preproc_version"],
            "source_run": charcnn["run_id"],
        },
        "gcb": {
            "role": "secondary_non_deciding",
            **gcb_fields,
            "fingerprint": gcb_fingerprint(gcb_fields),
            "source_run": gcb["run_id"],
        },
    }
    return {**files, MANIFEST_NAME: _json_bytes(doc)}, doc


def write_outputs(out: Path, outputs: Mapping[str, bytes], *, force: bool) -> None:
    """Refuse differing existing files (unless `force`), then write atomically, manifest last."""
    out = Path(out)
    conflicts = [rel for rel, data in outputs.items() if (out / rel).is_file() and (out / rel).read_bytes() != data]
    if conflicts and not force:
        raise BuildRefused(f"would overwrite differing files {sorted(conflicts)}; pass --force")
    for rel in sorted(r for r in outputs if r != MANIFEST_NAME):
        atomic_write_bytes(out / rel, outputs[rel])
    atomic_write_bytes(out / MANIFEST_NAME, outputs[MANIFEST_NAME])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build models/deploy/ (Jaccard val calibration, CharCNN v2 copy, sha256 manifest).",
    )
    p.add_argument("--charcnn-run", required=True, help="CharCNN v2 run dir (best.pth, calibration.json, config.json)")
    p.add_argument("--gcb-run", required=True, help="GraphCodeBERT SDD-3 run dir (config, thresholds_val, selection)")
    p.add_argument("--manifest", default=_rel(DEFAULT_MANIFEST), help="split_v1 manifest (default: %(default)s)")
    p.add_argument("--root", default=str(ROOT), help="corpus root the manifest ids are relative to")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output directory (default: models/deploy)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--force", action="store_true", help="overwrite existing files whose bytes differ")
    p.add_argument("--dry-run", action="store_true", help="run every check and print the manifest; write nothing")
    p.add_argument(
        "--limit-assignments", type=int, default=None,
        help="debug: first N val assignments only (refused for the default --out unless --dry-run)",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    try:
        check_out_dir(out)
        if args.limit_assignments is not None:
            if args.limit_assignments < 1:
                raise BuildRefused("--limit-assignments must be >= 1")
            if not args.dry_run and out.resolve() == DEFAULT_OUT.resolve():
                raise BuildRefused("--limit-assignments is debug only: use --dry-run or another --out")
        outputs, doc = build(args)
        if args.dry_run:
            print(json.dumps(doc, indent=2, sort_keys=True))
            return 0
        write_outputs(out, outputs, force=args.force)
    except BuildRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return REFUSED_EXIT
    a = doc["channel_a"]
    print(
        f"wrote {out}: channel_a {a['threshold_key']}={a['threshold']} (achieved FPR {a['achieved_fpr']}, "
        f"TPR {a['tpr']}); channel_b {doc['channel_b']['threshold_key']}={doc['channel_b']['threshold']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
