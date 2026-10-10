"""Split manifest loader: schema validation, file hashing, split filters and GT views.

Light by design (stdlib, plus numpy for `PairSet`): training and evaluation code import this
module, never the builder. The manifest does not embed its own hash; the loader computes it and
consumers record it (calibration files, run reports). `expected_sha256` refuses a file that
changed since a consumer recorded it.

The committed manifest is gzip (`split_v1.json.gz`); plain `.json` also loads. Gzip is detected
by its magic bytes, not the suffix. The sha256 is always taken over the DECOMPRESSED canonical
JSON bytes (`manifest_sha256`), so it does not depend on gzip level, header or zlib version, and
a `.json` and a `.json.gz` holding the same manifest share one hash.
"""

import gzip
import hashlib
import json
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "data" / "splits" / "split_v1.json.gz"
GZIP_MAGIC = b"\x1f\x8b"
SCHEMA = "graphito.split/v1"
SPLITS = ("train", "val", "test")
HELD_OUT_ORDER = ("test", "val", "train")
STRATA = ("lang", "source")
TOP_LEVEL_KEYS = ("schema", "config", "blocks", "groups", "entries", "stats")
ENTRY_KEYS = (
    "id", "course", "block", "assignment", "student", "lang", "source", "model", "profile",
    "sha256", "norm_hash", "n_tokens", "dup_group", "dup_rep", "cluster_id", "gt_status",
    "split", "excluded", "flags",
)
_ENUMS = {
    "split": set(SPLITS),
    "source": {"human", "ai"},
    "lang": {"c", "cpp"},
    "gt_status": {"positive", "negative", "ambiguous", "unlabeled", "n/a", None},
}


class ManifestError(ValueError):
    """The manifest is malformed or violates a split invariant."""


class ManifestHashError(ManifestError):
    """The manifest's sha256 differs from the one the caller expected."""


@dataclass(frozen=True)
class Sample:
    id: str
    course: str
    block: str
    assignment: str
    student: Optional[str]
    lang: str
    source: str
    model: Optional[str]
    profile: Optional[str]
    sha256: str
    norm_hash: str
    n_tokens: int
    dup_group: Optional[str]
    dup_rep: Optional[str]
    cluster_id: Optional[str]
    gt_status: Optional[str]
    split: str
    excluded: bool
    flags: Tuple[str, ...]

    @property
    def broken(self) -> bool:
        return "broken" in self.flags


@dataclass(frozen=True)
class PairSet:
    """Same-assignment human pairs; `a`/`b` index `ids` (a < b).

    `label`: 1 = same GT cluster, 0 = different clusters (a true negative pair), -1 = the pair
    involves an `ambiguous` entry (only with `include_ambiguous=True`; never a negative).
    `ambiguous` is the boolean mask of those pairs (all False by default).
    """

    a: np.ndarray
    b: np.ndarray
    label: np.ndarray
    assignment: np.ndarray
    ids: List[str]
    ambiguous: np.ndarray


def validate_schema(data: Mapping) -> None:
    """Raise ManifestError unless the top level and every entry match `graphito.split/v1`."""
    if not isinstance(data, Mapping):
        raise ManifestError("manifest root must be a JSON object")
    if data.get("schema") != SCHEMA:
        raise ManifestError(f"unknown manifest schema {data.get('schema')!r} (want {SCHEMA})")
    missing = [k for k in TOP_LEVEL_KEYS if k not in data]
    if missing:
        raise ManifestError(f"manifest lacks top-level keys {missing}")
    if not isinstance(data["entries"], list):
        raise ManifestError("manifest entries must be a list")
    for n, entry in enumerate(data["entries"]):
        if not isinstance(entry, Mapping):
            raise ManifestError(f"entry #{n} must be a JSON object, got {type(entry).__name__}")
        lacking = [k for k in ENTRY_KEYS if k not in entry]
        if lacking:
            raise ManifestError(f"entry {entry.get('id')} lacks keys {lacking}")
        for key, allowed in _ENUMS.items():
            value = entry[key]
            if not isinstance(value, (str, type(None))) or value not in allowed:
                raise ManifestError(f"entry {entry['id']} has invalid {key} {value!r}")
        if not isinstance(entry["flags"], list) or not all(isinstance(f, str) for f in entry["flags"]):
            raise ManifestError(f"entry {entry['id']} has invalid flags {entry['flags']!r}")
        if not isinstance(entry["excluded"], bool):
            raise ManifestError(f"entry {entry['id']} has invalid excluded {entry['excluded']!r}")


def check_invariants(entries: Iterable[Mapping]) -> None:
    """Raise ManifestError unless blocks, included dup groups and clusters each sit in one split
    and every split covers every lang/source present among included entries."""
    owner: Dict[Tuple[str, str], str] = {}
    present = set()
    have: Dict[str, set] = {s: set() for s in SPLITS}
    for e in entries:
        keys = [("block", e["block"])]
        if e["cluster_id"] is not None:
            keys.append(("cluster", e["cluster_id"]))
        if not e["excluded"]:
            if e["dup_group"] is not None:
                keys.append(("dup group", e["dup_group"]))
            for kind in STRATA:
                present.add((kind, e[kind]))
                have[e["split"]].add((kind, e[kind]))
        for key in keys:
            if owner.setdefault(key, e["split"]) != e["split"]:
                raise ManifestError(f"{key[0]} {key[1]} spans splits {owner[key]} and {e['split']}")
    gap = next(
        ((split, min(present - have[split])) for split in HELD_OUT_ORDER if present - have[split]),
        None,
    )
    if gap is not None:
        split, (kind, value) = gap
        raise ManifestError(f"split '{split}' lacks stratum {kind}={value}")


@dataclass(frozen=True)
class SplitManifest:
    path: Path
    sha256: str
    config: Dict
    stats: Dict
    blocks: Dict
    groups: Dict
    entries: Tuple[Sample, ...]
    _by_id: Dict[str, Sample] = field(repr=False, compare=False)

    def samples(
        self,
        split: Optional[str] = None,
        *,
        lang: Optional[str] = None,
        source: Optional[str] = None,
        course: Optional[str] = None,
        include_broken: bool = False,
        include_excluded: bool = False,
        representatives_only: bool = False,
    ) -> List[Sample]:
        """Filtered entries. Broken entries need `include_broken`; other exclusions
        (`cross_split_dup`) need `include_excluded`.

        `representatives_only` keeps one member per dup group: the smallest id among the
        group's members that pass every other filter. The manifest's global `dup_rep` is not
        used, since it may sit in another split or be excluded as `cross_split_dup`."""
        if split is not None and split not in SPLITS:
            raise ValueError(f"unknown split {split!r} (want one of {SPLITS})")
        out = []
        for s in self.entries:
            if s.broken and not include_broken:
                continue
            if s.excluded and not s.broken and not include_excluded:
                continue
            if (split and s.split != split) or (lang and s.lang != lang):
                continue
            if (source and s.source != source) or (course and s.course != course):
                continue
            out.append(s)
        if representatives_only:
            rep: Dict[str, str] = {}
            for s in out:
                if s.dup_group is not None and (s.dup_group not in rep or s.id < rep[s.dup_group]):
                    rep[s.dup_group] = s.id
            out = [s for s in out if s.dup_group is None or rep[s.dup_group] == s.id]
        return out

    def split_of(self, sample_id: str) -> str:
        return self._by_id[sample_id].split

    def clusters(self, split: Optional[str] = None) -> Dict[str, List[str]]:
        """GT cluster id -> sorted member ids (included entries only)."""
        out: Dict[str, List[str]] = {}
        for s in self.samples(split):
            if s.cluster_id is not None:
                out.setdefault(s.cluster_id, []).append(s.id)
        return {cid: sorted(members) for cid, members in sorted(out.items())}

    def channel_a_negatives(self, split: Optional[str] = None) -> List[Sample]:
        """Human entries labelled `negative`; unlabeled/ambiguous ones are never negatives."""
        return [s for s in self.samples(split, source="human") if s.gt_status == "negative"]

    def plagiarism_pairs(self, split: str, include_ambiguous: bool = False) -> PairSet:
        """All same-assignment pairs of labelled human entries of different students.

        By default only `positive`/`negative` entries pair, so labels are 1 or 0. With
        `include_ambiguous=True` pairs involving an `ambiguous` entry are added with label -1
        and `PairSet.ambiguous` True; they are never labelled 0 (not true negatives), so
        callers must filter them (e.g. `label[~ambiguous]`) before binary metrics."""
        allowed = {"positive", "negative"} | ({"ambiguous"} if include_ambiguous else set())
        pool = sorted(
            (s for s in self.samples(split, source="human") if s.gt_status in allowed),
            key=lambda s: (s.assignment, s.id),
        )
        ids = [s.id for s in pool]
        parts: List[Tuple[np.ndarray, ...]] = []
        start = 0
        while start < len(pool):
            assignment = pool[start].assignment
            stop = start
            while stop < len(pool) and pool[stop].assignment == assignment:
                stop += 1
            group = pool[start:stop]
            i, j = np.triu_indices(len(group), k=1)
            students = np.array([s.student for s in group], dtype=object)
            clusters = np.array([s.cluster_id or "" for s in group], dtype=object)
            unsure = np.array([s.gt_status == "ambiguous" for s in group], dtype=bool)
            keep = students[i] != students[j]
            i, j = i[keep], j[keep]
            label = ((clusters[i] == clusters[j]) & (clusters[i] != "")).astype(np.int8)
            ambiguous = unsure[i] | unsure[j]
            label[ambiguous] = -1
            parts.append(
                (i + start, j + start, label, np.full(i.size, assignment, dtype=object), ambiguous)
            )
            start = stop
        if not parts:
            empty = np.empty(0, dtype=np.int64)
            return PairSet(
                empty, empty, np.empty(0, dtype=np.int8), np.empty(0, dtype=object), ids,
                np.empty(0, dtype=bool),
            )
        a, b, label, assignment, ambiguous = (np.concatenate(cols) for cols in zip(*parts))
        return PairSet(a.astype(np.int64), b.astype(np.int64), label, assignment, ids, ambiguous)

    def check_invariants(self) -> None:
        check_invariants(asdict(s) for s in self.entries)


def read_manifest_bytes(path: "str | Path") -> bytes:
    """Canonical JSON bytes of a manifest file, decompressed when the file is gzip."""
    raw = Path(path).read_bytes()
    if raw[:2] != GZIP_MAGIC:
        return raw
    try:
        return gzip.decompress(raw)
    except (OSError, EOFError, zlib.error) as exc:
        raise ManifestError(f"{path}: corrupt gzip manifest ({exc})") from None


def manifest_sha256(path: "str | Path") -> str:
    """The manifest hash consumers record: sha256 of the decompressed canonical JSON bytes."""
    return hashlib.sha256(read_manifest_bytes(path)).hexdigest()


def load_manifest(
    path: "str | Path" = DEFAULT_MANIFEST, expected_sha256: Optional[str] = None
) -> SplitManifest:
    """Load (`.json` or `.json.gz`) and schema-validate a manifest; refuse it when
    `expected_sha256` does not match the sha256 of its decompressed bytes."""
    path = Path(path)
    raw = read_manifest_bytes(path)
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and expected_sha256.lower() != digest:
        raise ManifestHashError(f"{path}: sha256 {digest} does not match expected {expected_sha256}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{path}: not valid UTF-8 JSON ({exc})") from None
    validate_schema(data)
    entries = tuple(
        Sample(**{**{k: e[k] for k in ENTRY_KEYS}, "flags": tuple(e["flags"])}) for e in data["entries"]
    )
    return SplitManifest(
        path=path,
        sha256=digest,
        config=data["config"],
        stats=data["stats"],
        blocks=data["blocks"],
        groups=data["groups"],
        entries=entries,
        _by_id={s.id: s for s in entries},
    )


def load_split(
    split: str,
    *,
    path: "str | Path" = DEFAULT_MANIFEST,
    expected_sha256: Optional[str] = None,
    lang: Optional[str] = None,
    source: Optional[str] = None,
    course: Optional[str] = None,
    include_broken: bool = False,
) -> List[Sample]:
    """Entries of one split (excluded entries dropped; broken ones only with `include_broken`)."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r} (want one of {SPLITS})")
    manifest = load_manifest(path, expected_sha256)
    return manifest.samples(split, lang=lang, source=source, course=course, include_broken=include_broken)
