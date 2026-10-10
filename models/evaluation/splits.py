"""Split builder: discovery, hygiene flags and dedup grouping for the train/val/test manifest.

Disk is the source of truth (never `.generation_state.json`) and nothing is deleted or modified:
every exclusion is a flag. Exact duplicates (same `norm_hash`) are grouped globally; near
duplicates (identifier-normalized 5-token-shingle Jaccard >= threshold) only within a block, while
cross-block near duplicates are counted but never merged. See design "Split Algorithm".
"""

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

import numpy as np

from .dedup import (
    LSH_BANDS,
    LSH_ROWS,
    NUM_PERM,
    SHINGLE_K,
    UnionFind,
    jaccard,
    lsh_candidates,
    make_permutations,
    minhash,
    shingle_hashes,
    token_ids,
)
from .ground_truth import CLUSTER_ID_RULE, LABEL_RULE, HumanFile, parse_ground_truth, resolve_clusters
from .normalize import effective_length, norm_hash, shingle_tokens

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "graphito.split/v1"
BUILDER_VERSION = "1.0"

ENTRY_KEYS = (
    "id", "course", "block", "assignment", "student", "lang", "source", "model", "profile",
    "sha256", "norm_hash", "n_tokens", "dup_group", "dup_rep", "cluster_id", "gt_status",
    "split", "excluded", "flags",
)
EXTENSIONS = {".c": "c", ".cpp": "cpp"}
COPY_SUFFIX_RE = re.compile(r"\s\(\d+\)")  # same rule as data/golden_set/build_corpus.py
STUDENT_RE = re.compile(r"^student\d+$")
AI_NAME_RE = re.compile(r"^ref_(?P<profile>[a-z-]+)_or-(?P<model>.+)_\d{8}_\d{6}_\d+$")


@dataclass(frozen=True)
class SplitConfig:
    """Builder inputs. Unset roots default to the repository layout under `repo_root`."""

    seed: int = 42
    repo_root: Path = ROOT
    raw_root: Optional[Path] = None  # data/raw/src
    ai_root: Optional[Path] = None  # data/output
    gt_static: Optional[Path] = None  # data/raw/ground-truth-static-anon.txt
    gt_ambiguous: Tuple[Path, ...] = ()  # dynamic/full ground truth: marks `ambiguous` only
    test_fraction: float = 0.20
    val_fraction: float = 0.15
    min_blocks: int = 2
    max_attempts: int = 1000
    min_effective_bytes: int = 50
    threshold: float = 0.85
    sensitivity: Tuple[float, ...] = (0.80, 0.85, 0.90)
    shingle_k: int = SHINGLE_K
    num_perm: int = NUM_PERM
    bands: int = LSH_BANDS
    rows: int = LSH_ROWS
    minhash_seed: int = 0  # independent of `seed`: dup groups never depend on the split seed

    def roots(self) -> Tuple[Path, Path, Path]:
        repo = Path(self.repo_root)
        raw = Path(self.raw_root) if self.raw_root else repo / "data" / "raw" / "src"
        ai = Path(self.ai_root) if self.ai_root else repo / "data" / "output"
        gt = Path(self.gt_static) if self.gt_static else repo / "data" / "raw" / "ground-truth-static-anon.txt"
        return raw, ai, gt


class ScannedFile(NamedTuple):
    id: str  # repo-relative POSIX path
    source: str  # human | ai
    rel: str  # path relative to its source root
    path: Path


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{path} is not under repo_root {repo_root}") from None


def scan(raw_root: Path, ai_root: Path, repo_root: Path) -> List[ScannedFile]:
    """List every .c/.cpp file under the human and AI roots, sorted by repo-relative id."""
    files: List[ScannedFile] = []
    for source, root in (("human", Path(raw_root)), ("ai", Path(ai_root))):
        prefix = _repo_relative(root, repo_root)
        for path in root.rglob("*"):
            if path.suffix in EXTENSIONS and path.is_file():
                rel = path.relative_to(root).as_posix()
                files.append(ScannedFile(f"{prefix}/{rel}" if prefix != "." else rel, source, rel, path))
    return sorted(files, key=lambda f: f.id)


def parse_path(rel: str, source: str) -> Dict[str, object]:
    """Parse `<course>/<Zx>/<Zy>/<file>` into manifest metadata plus informational flags."""
    parts = rel.split("/")
    if len(parts) != 4:
        raise ValueError(f"unexpected layout (want <course>/<Zx>/<Zy>/<file>): {rel}")
    course, zx, zy, name = parts
    pure = PurePosixPath(name)
    if pure.suffix not in EXTENSIONS:
        raise ValueError(f"unsupported extension: {rel}")
    stem = COPY_SUFFIX_RE.sub("", pure.stem)
    meta: Dict[str, object] = {
        "course": course,
        "block": f"{course[:1]}/{zx}",
        "assignment": f"{course}/{zx}/{zy}",
        "student": None,
        "lang": EXTENSIONS[pure.suffix],
        "model": None,
        "profile": None,
        "flags": [],
    }
    if source == "human":
        meta["student"] = stem if STUDENT_RE.match(stem) else None
    else:
        match = AI_NAME_RE.match(stem)
        if match:
            meta["model"], meta["profile"] = match.group("model"), match.group("profile")
        else:
            meta["flags"] = ["unparsed_name"]
    return meta


def _decode(data: bytes) -> Tuple[str, bool]:
    try:
        return data.decode("utf-8-sig"), False
    except UnicodeDecodeError:
        return data.decode("latin-1"), True


def _broken_reasons(
    filename: str, text: str, n_bytes: int, source: str, student: Optional[str], min_bytes: int
) -> List[str]:
    reasons = []
    if n_bytes == 0:
        reasons.append("empty")
    elif effective_length(text) < min_bytes:
        reasons.append("too_short")
    if source == "human" and student is None:
        reasons.append("no_student_id")
    if COPY_SUFFIX_RE.search(filename):
        reasons.append("copy_suffix")
    return sorted(["broken", *reasons]) if reasons else []


def hygiene_flags(
    filename: str, data: bytes, source: str, student: Optional[str], min_effective_bytes: int = 50
) -> List[str]:
    """Sorted `broken` flag plus its sub-flags (`empty|too_short|no_student_id|copy_suffix`)."""
    return _broken_reasons(
        filename, _decode(data)[0], len(data), source, student, min_effective_bytes
    )


def dup_group_id(rep: str) -> str:
    """Stable group id from the smallest member id (unaffected by unrelated files)."""
    return "dg-" + hashlib.sha256(rep.encode("utf-8")).hexdigest()[:10]


@dataclass
class _Dedup:
    groups: Dict[int, List[int]]  # operative root index -> sorted member indices
    sensitivity: Dict[float, Dict[int, List[int]]]
    near_edges: List[Tuple[int, int, float]]  # verified same-block pairs >= operative threshold
    cross_near_pairs: List[Tuple[int, int]]  # verified cross-block pairs between distinct groups
    cross_block_components: int


def _dedup(
    entries: List[Dict], shingles: Dict[int, np.ndarray], config: SplitConfig
) -> _Dedup:
    live = sorted(shingles)
    thresholds = sorted(set(config.sensitivity) | {config.threshold})
    ufs = {t: UnionFind(live) for t in thresholds}
    strictest = ufs[thresholds[-1]]

    # Exact groups: global, keyed by norm_hash.
    first_by_hash: Dict[str, int] = {}
    rep_of: Dict[Tuple[str, str], int] = {}  # one MinHash representative per (norm_hash, block)
    for i in live:
        nh, block = entries[i]["norm_hash"], entries[i]["block"]
        root = first_by_hash.setdefault(nh, i)
        if root != i:
            for uf in ufs.values():
                uf.union(root, i)
        rep_of.setdefault((nh, block), i)

    a, b = make_permutations(config.num_perm, config.minhash_seed)
    reps = sorted(rep_of.values())
    sigs = {i: minhash(shingles[i], a, b) for i in reps}

    # Near-dup groups: LSH candidates within each block, verified by exact Jaccard.
    by_block: Dict[str, List[int]] = {}
    for i in reps:
        by_block.setdefault(entries[i]["block"], []).append(i)
    near_edges: List[Tuple[int, int, float]] = []
    for block in sorted(by_block):
        members = by_block[block]
        if len(members) < 2:
            continue
        matrix = np.stack([sigs[i] for i in members])
        for x, y in lsh_candidates(matrix, config.bands, config.rows):
            p, q = members[x], members[y]
            both_human = entries[p]["source"] == entries[q]["source"] == "human"
            if strictest.connected(p, q) and not both_human:
                continue  # already joined at every threshold; human pairs still feed GT stats
            sim = jaccard(shingles[p], shingles[q])
            for t in thresholds:
                if sim >= t:
                    ufs[t].union(p, q)
            if sim >= config.threshold:
                near_edges.append((p, q, sim))

    operative = ufs[config.threshold]
    groups = operative.groups()

    # Cross-block near-dups: one representative per (group, block), counted but never merged.
    group_of = {i: operative.find(i) for i in live}
    group_rep: Dict[Tuple[int, str], int] = {}
    for i in reps:
        group_rep.setdefault((group_of[i], entries[i]["block"]), i)
    cross_reps = sorted(group_rep.values())
    cross_pairs: List[Tuple[int, int]] = []
    linked = UnionFind(groups)
    if len(cross_reps) >= 2:
        matrix = np.stack([sigs[i] for i in cross_reps])
        for x, y in lsh_candidates(matrix, config.bands, config.rows):
            p, q = cross_reps[x], cross_reps[y]
            if entries[p]["block"] == entries[q]["block"] or group_of[p] == group_of[q]:
                continue
            if jaccard(shingles[p], shingles[q]) >= config.threshold:
                cross_pairs.append((p, q))
                linked.union(group_of[p], group_of[q])
    components = 0
    for roots in linked.groups().values():
        blocks = {entries[m]["block"] for r in roots for m in groups[r]}
        components += len(blocks) > 1

    return _Dedup(
        groups=groups,
        sensitivity={t: ufs[t].groups() for t in config.sensitivity},
        near_edges=near_edges,
        cross_near_pairs=cross_pairs,
        cross_block_components=components,
    )


def _merge_gt(paths: Sequence[Path]) -> Dict[str, List[Set[str]]]:
    merged: Dict[str, List[Set[str]]] = {}
    for path in paths:
        for assignment, lines in parse_ground_truth(path).items():
            merged.setdefault(assignment, []).extend(lines)
    return merged


def _tick(timings: Optional[Dict[str, float]], stage: str, start: float) -> float:
    now = time.perf_counter()
    if timings is not None:
        timings[stage] = round(now - start, 3)
    return now


def _threshold_key(t: float) -> str:
    return f"{t:.2f}"


def build_split(config: SplitConfig, timings: Optional[Dict[str, float]] = None) -> Dict:
    """Build the split manifest dict. Per-stage seconds go to `timings`, never into the manifest."""
    raw_root, ai_root, gt_path = config.roots()
    clock = time.perf_counter()
    files = scan(raw_root, ai_root, config.repo_root)
    clock = _tick(timings, "scan", clock)

    entries: List[Dict] = []
    shingles: Dict[int, np.ndarray] = {}
    for index, f in enumerate(files):
        data = f.path.read_bytes()
        text, non_utf8 = _decode(data)
        meta = parse_path(f.rel, f.source)
        broken = _broken_reasons(
            PurePosixPath(f.rel).name, text, len(data), f.source, meta["student"],
            config.min_effective_bytes,
        )
        flags = sorted(set(meta.pop("flags")) | set(broken) | ({"non_utf8"} if non_utf8 else set()))
        tokens = shingle_tokens(text)
        entries.append(
            {
                "id": f.id,
                "source": f.source,
                **meta,
                "sha256": hashlib.sha256(data).hexdigest(),
                "norm_hash": norm_hash(text),
                "n_tokens": len(tokens),
                "dup_group": None,
                "dup_rep": None,
                "cluster_id": None,
                "gt_status": None,
                "split": None,
                "excluded": bool(broken),
                "flags": flags,
            }
        )
        if not broken:
            shingles[index] = shingle_hashes(token_ids(tokens), config.shingle_k)
    clock = _tick(timings, "read_normalize", clock)

    dd = _dedup(entries, shingles, config)
    for root, members in dd.groups.items():
        rep = entries[root]["id"]
        gid = dup_group_id(rep)
        for m in members:
            entries[m]["dup_group"], entries[m]["dup_rep"] = gid, rep
    clock = _tick(timings, "dedup", clock)

    gt = parse_ground_truth(gt_path)
    humans = [
        HumanFile(e["id"], e["assignment"], e["student"] or "", e["excluded"])
        for e in entries
        if e["source"] == "human"
    ]
    resolution = resolve_clusters(gt, humans, _merge_gt(config.gt_ambiguous) or None)
    for e in entries:
        if e["source"] == "ai":
            e["gt_status"] = "n/a"
        elif not e["excluded"]:
            e["gt_status"] = resolution.gt_status[e["id"]]
            e["cluster_id"] = resolution.cluster_of.get(e["id"])
    clock = _tick(timings, "ground_truth", clock)

    return {
        "schema": SCHEMA,
        "config": _config_section(config, raw_root, ai_root, gt_path),
        "entries": entries,
        "stats": {
            "cross_block_dup_groups": dd.cross_block_components,
            "dup_threshold_sensitivity": {
                _threshold_key(t): len(g) for t, g in dd.sensitivity.items()
            },
            "unresolved_cluster_members": resolution.unresolved,
            "dedup": {"cross_block_near_pairs": len(dd.cross_near_pairs)},
        },
    }


def _config_section(config: SplitConfig, raw_root: Path, ai_root: Path, gt_path: Path) -> Dict:
    repo = config.repo_root
    return {
        "builder_version": BUILDER_VERSION,
        "seed": config.seed,
        "roots": {"raw": _repo_relative(raw_root, repo), "ai": _repo_relative(ai_root, repo)},
        "group_key": "course_letter/Zx",
        "fractions": {"target": {"test": config.test_fraction, "val": config.val_fraction}},
        "min_blocks_per_split": config.min_blocks,
        "hygiene": {
            "min_effective_bytes": config.min_effective_bytes,
            "copy_suffix_regex": COPY_SUFFIX_RE.pattern,
        },
        "dedup": {
            "threshold": config.threshold,
            "sensitivity": [_threshold_key(t) for t in config.sensitivity],
            "shingle_k": config.shingle_k,
            "num_perm": config.num_perm,
            "bands": config.bands,
            "rows": config.rows,
            "minhash_seed": config.minhash_seed,
            "exact_scope": "global",
            "near_scope": "block",
        },
        "ground_truth": {
            "static": _repo_relative(gt_path, repo),
            "ambiguous": [_repo_relative(p, repo) for p in config.gt_ambiguous],
            "cluster_id_rule": CLUSTER_ID_RULE,
            "label_rule": LABEL_RULE,
        },
    }
