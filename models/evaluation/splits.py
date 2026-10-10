"""Split builder: group-level, seeded, deterministic train/val/test manifest.

Disk is the source of truth (never `.generation_state.json`) and nothing is deleted or modified:
every exclusion is a flag. Exact duplicates (same `norm_hash`) are grouped globally; near
duplicates (identifier-normalized 5-token-shingle Jaccard >= threshold) only within a block, while
cross-block near duplicates are counted but never merged. A block is one assignment with its
years merged (course letter + Zx + Zy: `A2016/Z3/Z1` and `A2017/Z3/Z1` form `A/Z3/Z1`); the
`zx_block` option keeps the older letter + Zx unit. Whole blocks are assigned to splits; a dup
group spanning blocks in different splits is pinned to its most held-out split and its other
members are excluded (`cross_split_dup`). Sibling assignments of one Zx may land in different
splits: `stats.zx_groups_split` and `stats.dedup.cross_split_near_pairs` quantify that topic
leakage. GT clusters live inside one assignment, so they never span splits; a student clustered
in several blocks is reported as overlap, not merged. See design "Split Algorithm".
"""

import hashlib
import json
import math
import os
import re
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
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
from .manifest import (  # schema constants live with the loader; re-exported here
    ENTRY_KEYS,  # noqa: F401
    HELD_OUT_ORDER,  # pin target preference: test > val > train
    SCHEMA,
    SPLITS,
    STRATA,
    check_invariants,
    validate_schema,
)
from .normalize import effective_length, norm_hash, shingle_tokens
from .provenance import atomic_write_bytes
from .seed import stable_rng

ROOT = Path(__file__).resolve().parents[2]
BUILDER_VERSION = "1.1"
_PARALLEL_MIN = 2000  # below this many files a process pool costs more than it saves
MIN_EFFECTIVE_BYTES = 50  # hygiene: below this effective length a file is `too_short`

EXTENSIONS = {".c": "c", ".cpp": "cpp"}
COPY_SUFFIX_RE = re.compile(r"\s\(\d+\)")  # same rule as data/golden_set/build_corpus.py
STUDENT_RE = re.compile(r"^student\d+$")
AI_NAME_RE = re.compile(r"^ref_(?P<profile>[a-z-]+)_or-(?P<model>.+)_\d{8}_\d{6}_\d+$")
# Split unit (`SplitConfig.group_key`) -> the rule recorded in `config.group_key`.
GROUP_KEYS = {"assignment": "letter/Zx/Zy (years merged)", "zx_block": "letter/Zx (years merged)"}


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
    group_key: str = "assignment"  # split unit, see GROUP_KEYS
    min_blocks: int = 2
    max_attempts: int = 1000
    min_effective_bytes: int = MIN_EFFECTIVE_BYTES
    threshold: float = 0.85
    sensitivity: Tuple[float, ...] = (0.80, 0.85, 0.90)
    shingle_k: int = SHINGLE_K
    num_perm: int = NUM_PERM
    bands: int = LSH_BANDS
    rows: int = LSH_ROWS
    minhash_seed: int = 0  # independent of `seed`: dup groups never depend on the split seed
    workers: int = 0  # file-analysis processes; 0 = auto (serial below _PARALLEL_MIN files)

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


def block_key(course: str, zx: str, zy: str, group_key: str = "assignment") -> str:
    """Split block of an assignment: `A/Z3/Z1` (years merged), or `A/Z3` with `zx_block`."""
    if group_key not in GROUP_KEYS:
        raise ValueError(f"unknown group_key {group_key!r} (want one of {sorted(GROUP_KEYS)})")
    letter = course[:1]
    return f"{letter}/{zx}/{zy}" if group_key == "assignment" else f"{letter}/{zx}"


def parse_path(rel: str, source: str, group_key: str = "assignment") -> Dict[str, object]:
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
        "block": block_key(course, zx, zy, group_key),
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
    filename: str,
    data: bytes,
    source: str,
    student: Optional[str],
    min_effective_bytes: int = MIN_EFFECTIVE_BYTES,
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


def _analyze_file(task: Tuple[ScannedFile, int, int, str]) -> Tuple[Dict, Optional[np.ndarray]]:
    """Read one file and build its entry plus shingle hashes (None when broken).

    Top-level so a process pool can run it; the result depends only on the file bytes.
    """
    f, min_bytes, shingle_k, group_key = task
    data = f.path.read_bytes()
    text, non_utf8 = _decode(data)
    meta = parse_path(f.rel, f.source, group_key)
    broken = _broken_reasons(
        PurePosixPath(f.rel).name, text, len(data), f.source, meta["student"], min_bytes
    )
    flags = sorted(set(meta.pop("flags")) | set(broken) | ({"non_utf8"} if non_utf8 else set()))
    tokens = shingle_tokens(text)
    entry = {
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
    return entry, None if broken else shingle_hashes(token_ids(tokens), shingle_k)


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
    if config.group_key not in GROUP_KEYS:
        raise ValueError(f"unknown group_key {config.group_key!r} (want one of {sorted(GROUP_KEYS)})")
    raw_root, ai_root, gt_path = config.roots()
    clock = time.perf_counter()
    files = scan(raw_root, ai_root, config.repo_root)
    clock = _tick(timings, "scan", clock)

    tasks = [(f, config.min_effective_bytes, config.shingle_k, config.group_key) for f in files]
    workers = config.workers or (min(8, os.cpu_count() or 1) if len(files) >= _PARALLEL_MIN else 1)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:  # map() keeps input order
            analyzed = list(pool.map(_analyze_file, tasks, chunksize=128))
    else:
        analyzed = [_analyze_file(t) for t in tasks]
    entries = [entry for entry, _ in analyzed]
    shingles = {i: sh for i, (_, sh) in enumerate(analyzed) if sh is not None}
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

    multi_block = [
        members
        for members in dd.groups.values()
        if len({entries[m]["block"] for m in members}) > 1
    ]
    assignment = _assign_blocks(entries, multi_block, config)
    for e in entries:
        e["split"] = assignment.block_split[e["block"]]
    for m in assignment.pinned:
        entries[m]["excluded"] = True
        entries[m]["flags"] = sorted(entries[m]["flags"] + ["cross_split_dup"])
    clock = _tick(timings, "assign", clock)

    config_section = _config_section(config, raw_root, ai_root, gt_path)
    config_section["fractions"]["actual"] = assignment.plans
    config_section["attempt"] = assignment.attempt
    manifest = {
        "schema": SCHEMA,
        "config": config_section,
        "blocks": _blocks_section(entries),
        "groups": _groups_section(entries, dd, resolution, assignment.block_split, config.group_key),
        "entries": entries,
        "stats": _stats(entries, dd, resolution, assignment, config),
    }
    validate(manifest)
    _tick(timings, "stats_validate", clock)
    return manifest


# --- block assignment ---------------------------------------------------------------------------


@dataclass
class _Assignment:
    block_split: Dict[str, str]
    pinned: Set[int]  # entry indices excluded as cross_split_dup
    pinned_groups: int
    attempt: int
    plans: Dict[str, Dict[str, object]]  # letter -> block counts and fractions


def _plan(letter: str, n: int, config: SplitConfig) -> Dict[str, object]:
    # round() guards against float noise such as 0.15 * 20 = 3.0000000000000004
    n_test = max(config.min_blocks, math.ceil(round(config.test_fraction * n, 9)))
    n_val = max(config.min_blocks, math.ceil(round(config.val_fraction * n, 9)))
    n_train = n - n_test - n_val
    if n_train < 1:
        raise ValueError(
            f"course letter {letter} has {n} blocks: the {config.min_blocks}-block minimum for "
            f"test and val plus one train block cannot be met"
        )
    return {
        "n_blocks": n,
        "test": n_test,
        "val": n_val,
        "train": n_train,
        "test_fraction": round(n_test / n, 6),
        "val_fraction": round(n_val / n, 6),
        "train_fraction": round(n_train / n, 6),
    }


def _pin(
    entries: List[Dict], multi_block: List[List[int]], block_split: Dict[str, str]
) -> Tuple[Set[int], int]:
    pinned: Set[int] = set()
    groups = 0
    for members in multi_block:
        splits = {block_split[entries[m]["block"]] for m in members}
        if len(splits) < 2:
            continue
        target = min(splits, key=HELD_OUT_ORDER.index)
        groups += 1
        pinned.update(m for m in members if block_split[entries[m]["block"]] != target)
    return pinned, groups


def _assign_blocks(
    entries: List[Dict], multi_block: List[List[int]], config: SplitConfig
) -> _Assignment:
    blocks_by_letter: Dict[str, List[str]] = {}
    for block in sorted({e["block"] for e in entries}):
        blocks_by_letter.setdefault(block.split("/", 1)[0], []).append(block)
    plans = {L: _plan(L, len(b), config) for L, b in sorted(blocks_by_letter.items())}

    live = [i for i, e in enumerate(entries) if not e["excluded"]]
    block_strata: Dict[str, Counter] = {}
    for i in live:
        block_strata.setdefault(entries[i]["block"], Counter()).update(
            (kind, entries[i][kind]) for kind in STRATA
        )
    required = sorted({key for c in block_strata.values() for key in c})
    for key in required:
        holders = sum(1 for c in block_strata.values() if c[key])
        if holders < len(SPLITS):
            raise ValueError(
                f"stratum {key[0]}={key[1]} appears in only {holders} block(s); every split needs it"
            )

    missing = ""
    for attempt in range(config.max_attempts):
        block_split: Dict[str, str] = {}
        for letter, blocks in blocks_by_letter.items():
            order = list(blocks)
            stable_rng(config.seed, f"{letter}:{attempt}").shuffle(order)
            n_test, n_val = plans[letter]["test"], plans[letter]["val"]
            for k, block in enumerate(order):
                block_split[block] = "test" if k < n_test else "val" if k < n_test + n_val else "train"
        pinned, pinned_groups = _pin(entries, multi_block, block_split)
        have = {s: Counter() for s in SPLITS}
        for block, counts in block_strata.items():
            have[block_split[block]].update(counts)
        for m in pinned:
            have[block_split[entries[m]["block"]]].subtract((kind, entries[m][kind]) for kind in STRATA)
        gaps = [(s, key) for s in HELD_OUT_ORDER for key in required if have[s][key] <= 0]
        if not gaps:
            return _Assignment(block_split, pinned, pinned_groups, attempt, plans)
        split, (kind, value) = gaps[0]
        missing = f"{kind}={value} in split '{split}'"
    raise ValueError(f"no block assignment covers stratum {missing} after {config.max_attempts} attempts")


# --- validation ---------------------------------------------------------------------------------


def validate(manifest: Dict) -> None:
    """Raise ValueError unless blocks, included dup groups and clusters each sit in one split
    and every split covers every lang/source present among included entries.

    Same checks as the loader (`manifest.validate_schema` + `manifest.check_invariants`);
    `ManifestError` is a ValueError.
    """
    validate_schema(manifest)
    check_invariants(manifest["entries"])


# --- manifest sections --------------------------------------------------------------------------


def _blocks_section(entries: List[Dict]) -> Dict[str, Dict]:
    blocks: Dict[str, Dict] = {}
    for e in entries:
        info = blocks.setdefault(e["block"], {"split": e["split"], "courses": set(), "n_samples": 0})
        info["courses"].add(e["course"])
        info["n_samples"] += 1
    for info in blocks.values():
        info["courses"] = sorted(info["courses"])
    return blocks


def _groups_section(entries, dd: _Dedup, resolution, block_split: Dict[str, str], group_key: str) -> Dict:
    dup: Dict[str, Dict] = {}
    for root, members in dd.groups.items():
        if len(members) < 2:
            continue
        hashes = {entries[m]["norm_hash"] for m in members}
        blocks = sorted({entries[m]["block"] for m in members})
        kind = "exact" if len(hashes) == 1 else "near" if len(hashes) == len(members) else "mixed"
        dup[entries[root]["dup_group"]] = {
            "members": [entries[m]["id"] for m in members],
            "kind": kind,
            "blocks": blocks,
            "cross_block": len(blocks) > 1,
        }
    clusters = {
        cid: {
            "members": list(c.members),
            "students": list(c.students),
            "unresolved": list(c.unresolved),
            "split": block_split[_block_of_assignment(c.assignment, group_key)],
        }
        for cid, c in resolution.clusters.items()
    }
    return {"dup": dup, "clusters": clusters}


def _block_of_assignment(assignment: str, group_key: str) -> str:
    return block_key(*assignment.split("/"), group_key)


def _zx_groups_split(block_split: Dict[str, str]) -> Dict[str, Dict[str, int]]:
    """Per topic (`letter/Zx`): how many of its blocks each split holds (sibling leakage)."""
    out: Dict[str, Dict[str, int]] = {}
    for block, split in sorted(block_split.items()):
        letter, zx = block.split("/")[:2]
        out.setdefault(f"{letter}/{zx}", {s: 0 for s in SPLITS})[split] += 1
    return out


def _overlap(students: Dict[str, Set[str]]) -> Dict[str, int]:
    pairs = (("train", "val"), ("train", "test"), ("val", "test"))
    out = {f"{a}-{b}": sum(1 for s in students.values() if {a, b} <= s) for a, b in pairs}
    out["n_multi_split"] = sum(1 for s in students.values() if len(s) > 1)
    return out


def _stats(entries, dd: _Dedup, resolution, assignment: _Assignment, config: SplitConfig) -> Dict:
    included = [e for e in entries if not e["excluded"]]
    counts: Dict[str, Dict[str, Dict[str, int]]] = {s: {} for s in SPLITS}
    for e in included:
        by_lang = counts[e["split"]].setdefault(e["source"], {})
        by_lang[e["lang"]] = by_lang.get(e["lang"], 0) + 1

    overall: Dict[str, Set[str]] = {}
    by_letter: Dict[str, Dict[str, Set[str]]] = {}
    for e in included:
        if e["source"] == "human" and e["student"]:
            overall.setdefault(e["student"], set()).add(e["split"])
            letter = e["course"][:1]
            by_letter.setdefault(letter, {}).setdefault(e["student"], set()).add(e["split"])

    block_split = assignment.block_split
    cluster_split = {
        cid: block_split[_block_of_assignment(c.assignment, config.group_key)]
        for cid, c in resolution.clusters.items()
    }
    clusters_by_split = {s: 0 for s in SPLITS}
    for split in cluster_split.values():
        clusters_by_split[split] += 1
    cross_split_students = sum(
        1
        for cids in resolution.student_clusters.values()
        if len({cluster_split[c] for c in cids if c in cluster_split}) > 1
    )

    neg_pairs = _negative_near_dup_pairs(entries, dd)
    neg_by_split = {s: 0 for s in SPLITS}
    for a, _ in neg_pairs:
        neg_by_split[entries[a]["split"]] += 1  # same assignment, hence same block and split

    live_groups = list(dd.groups.values())
    hashes_live: Counter = Counter(entries[i]["norm_hash"] for g in live_groups for i in g)
    sensitivity_detail = {
        _threshold_key(t): {
            "n_groups": len(g),
            "n_samples_in_multi": sum(len(m) for m in g.values() if len(m) > 1),
            "max_size": max((len(m) for m in g.values()), default=0),
        }
        for t, g in dd.sensitivity.items()
    }
    return {
        "n_entries": len(entries),
        "n_included": len(included),
        "counts": counts,
        "excluded": {
            "broken": sum("broken" in e["flags"] for e in entries),
            "cross_split_dup": len(assignment.pinned),
        },
        "blocks": assignment.plans,
        "zx_groups_split": _zx_groups_split(block_split),
        "student_overlap": {
            "overall": _overlap(overall),
            "by_letter": {L: _overlap(s) for L, s in sorted(by_letter.items())},
        },
        "hygiene": dict(Counter(f for e in entries for f in e["flags"])),
        "cross_block_dup_groups": dd.cross_block_components,
        "dup_threshold_sensitivity": {k: v["n_groups"] for k, v in sensitivity_detail.items()},
        "unresolved_cluster_members": resolution.unresolved,
        "dedup": {
            "exact_groups": sum(1 for n in hashes_live.values() if n > 1),
            "sensitivity": sensitivity_detail,
            "mixed_source_groups": sum(
                1 for g in live_groups if len({entries[i]["source"] for i in g}) > 1
            ),
            "cross_block_exact_groups": sum(
                1 for g in live_groups if len({entries[i]["block"] for i in g}) > 1
            ),
            "cross_block_near_pairs": len(dd.cross_near_pairs),
            "cross_split_near_pairs": sum(
                1
                for p, q in dd.cross_near_pairs
                if block_split[entries[p]["block"]] != block_split[entries[q]["block"]]
            ),
            "pinned_groups": assignment.pinned_groups,
            "pinned_exclusions": len(assignment.pinned),
            "size_distribution": {str(k): v for k, v in Counter(len(g) for g in live_groups).items()},
        },
        "gt": {
            "clusters_by_split": clusters_by_split,
            "merged_lines": resolution.merged_lines,
            "unlabeled_courses": resolution.unlabeled_courses,
            "unlabeled_assignments": resolution.unlabeled_assignments,
            "cross_split_student_clusters": cross_split_students,
            "negative_near_dup": {
                "by_split": neg_by_split,
                "pairs": [[entries[a]["id"], entries[b]["id"]] for a, b in neg_pairs],
            },
        },
    }


def _negative_near_dup_pairs(entries: List[Dict], dd: _Dedup) -> List[Tuple[int, int]]:
    """Verified same-assignment human pairs of different students, both GT negatives."""

    def eligible(p: int, q: int) -> bool:
        a, b = entries[p], entries[q]
        return (
            a["gt_status"] == b["gt_status"] == "negative"
            and a["assignment"] == b["assignment"]
            and a["student"] != b["student"]
        )

    found: Set[Tuple[int, int]] = set()
    for p, q, _ in dd.near_edges:
        if eligible(p, q):
            found.add((min(p, q), max(p, q)))
    by_hash: Dict[Tuple[str, str], List[int]] = {}
    for members in dd.groups.values():
        for m in members:
            if entries[m]["gt_status"] == "negative":
                by_hash.setdefault((entries[m]["norm_hash"], entries[m]["assignment"]), []).append(m)
    for members in by_hash.values():
        for x, p in enumerate(members):
            for q in members[x + 1 :]:
                if eligible(p, q):
                    found.add((min(p, q), max(p, q)))
    return sorted(found)


# --- serialization ------------------------------------------------------------------------------


def dumps_manifest(manifest: Dict) -> str:
    """Deterministic JSON text: sorted keys, ASCII, LF, one entry per line, trailing newline."""

    def dump(value) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    parts = []
    for key in sorted(manifest):
        if key == "entries":
            body = ",\n".join(dump(e) for e in manifest["entries"])
            value = f"[\n{body}\n]" if body else "[]"
        else:
            value = dump(manifest[key])
        parts.append(f"{dump(key)}:{value}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def write_manifest(manifest: Dict, path: "str | Path") -> Path:
    """Write `dumps_manifest` output as UTF-8 bytes (no platform newline translation).

    Atomic (`provenance.atomic_write_bytes`): a failed write leaves any previous manifest
    intact and no temp file behind."""
    return atomic_write_bytes(path, dumps_manifest(manifest).encode("utf-8"))


def _config_section(config: SplitConfig, raw_root: Path, ai_root: Path, gt_path: Path) -> Dict:
    repo = config.repo_root
    return {
        "builder_version": BUILDER_VERSION,
        "seed": config.seed,
        "roots": {"raw": _repo_relative(raw_root, repo), "ai": _repo_relative(ai_root, repo)},
        "group_key": GROUP_KEYS[config.group_key],
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
