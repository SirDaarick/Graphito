"""Within-assignment pair scoring, views and MAP@R (spec GV1, GV3.1, GV4; design "Pair scoring").

`SplitManifest.plagiarism_pairs(split)` returns labelled human pairs (ambiguous and unlabeled
entries excluded) whose `a`/`b` index `ids`, and `ids` are sorted by (assignment, id), so every
assignment owns one contiguous block `ids[start:stop]`. Scoring never gathers pair-sized
embedding matrices: per assignment `g` a similarity method returns the block matrix `S_g`
(`[n_g, n_g]`; cosine `E_g E_g^T` of L2-normalized embeddings, or a set Jaccard), and the pair
score is `S_g[a - start, b - start]`. The same `S_g` feeds MAP@R for that assignment.

Views (GV4): `all` keeps every labelled pair; `no_identical` drops label-0 pairs whose files have
equal `norm_hash` (label-1 pairs are kept). In MAP@R the same rule sets identical-hash, not
same-cluster candidates to `-inf`, which is equivalent to removing them from the ranking.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from models.evaluation import metrics as M
from models.evaluation.manifest import PairSet, Sample, SplitManifest

__all__ = [
    "VIEWS",
    "EvalPairs",
    "ScoredPairs",
    "BlockSimilarity",
    "embedding_similarity",
    "stack_embeddings",
    "score_pairs",
    "map_at_r_ci",
    "restrict_pairs",
]

VIEWS = ("all", "no_identical")

BlockSimilarity = Callable[[int, int], np.ndarray]


def restrict_pairs(pairs: PairSet, assignments: Sequence[str], id_assignment: Sequence[str]) -> PairSet:
    """The pairs and ids of the given assignments only (`id_assignment[i]` is the assignment of
    `pairs.ids[i]`, so ids without a pair stay as MAP@R candidates), `a`/`b` re-indexed."""
    wanted = set(assignments)
    keep_ids = [i for i in range(len(pairs.ids)) if id_assignment[i] in wanted]
    remap = np.full(len(pairs.ids), -1, dtype=np.int64)
    remap[keep_ids] = np.arange(len(keep_ids))
    mask = np.isin(pairs.assignment, list(wanted))
    return PairSet(
        remap[pairs.a[mask]], remap[pairs.b[mask]], pairs.label[mask], pairs.assignment[mask],
        [pairs.ids[i] for i in keep_ids], pairs.ambiguous[mask],
    )


def _pair_count(group: Sequence[Sample], involved: Callable[[Sample], bool]) -> int:
    """Different-student pairs of `group` with at least one `involved` member."""
    n = 0
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            if group[i].student != group[j].student and (involved(group[i]) or involved(group[j])):
                n += 1
    return n


def _exclusions(manifest: SplitManifest, split: str, assignments: Optional[set]) -> Dict[str, int]:
    humans = [s for s in manifest.samples(split, source="human") if assignments is None or s.assignment in assignments]
    by_assignment: Dict[str, List[Sample]] = {}
    for s in humans:
        by_assignment.setdefault(s.assignment, []).append(s)
    labelled = {"positive", "negative"}
    return {
        "ambiguous_files": sum(s.gt_status == "ambiguous" for s in humans),
        "unlabeled_files": sum(s.gt_status not in labelled | {"ambiguous"} for s in humans),
        "ambiguous_pairs": sum(
            _pair_count([s for s in g if s.gt_status in labelled | {"ambiguous"}], lambda s: s.gt_status == "ambiguous")
            for g in by_assignment.values()
        ),
        "unlabeled_pairs": sum(
            _pair_count(g, lambda s: s.gt_status not in labelled | {"ambiguous"}) for g in by_assignment.values()
        ),
    }


@dataclass(frozen=True)
class EvalPairs:
    """Labelled pairs of one split with per-id metadata and assignment blocks.

    `samples[i]` is the manifest entry of `pairs.ids[i]`; `blocks` are `(assignment, start, stop)`
    over `pairs.ids`; `pair_index[assignment]` are the pair rows of that assignment."""

    split: str
    pairs: PairSet
    samples: Tuple[Sample, ...]
    blocks: Tuple[Tuple[str, int, int], ...]
    pair_index: Dict[str, np.ndarray]
    exclusions: Dict[str, int] = field(default_factory=dict)
    same_student_pairs: int = 0

    @classmethod
    def build(
        cls,
        pairs: PairSet,
        samples_by_id: Mapping[str, Sample],
        *,
        split: Optional[str] = None,
        exclusions: Optional[Mapping[str, int]] = None,
    ) -> "EvalPairs":
        samples = tuple(samples_by_id[i] for i in pairs.ids)
        blocks: List[Tuple[str, int, int]] = []
        start = 0
        while start < len(samples):
            stop = start
            while stop < len(samples) and samples[stop].assignment == samples[start].assignment:
                stop += 1
            blocks.append((samples[start].assignment, start, stop))
            start = stop
        names = [b[0] for b in blocks]
        if len(set(names)) != len(names):
            raise ValueError("pair ids are not contiguous per assignment")
        bounds = {name: (s, e) for name, s, e in blocks}
        pair_index = {}
        for name in names:
            rows = np.flatnonzero(pairs.assignment == name)
            s, e = bounds[name]
            if rows.size and not (
                (pairs.a[rows] >= s).all() and (pairs.b[rows] < e).all() and (pairs.a[rows] < pairs.b[rows]).all()
            ):
                raise ValueError(f"pairs of {name} index ids outside its block")
            pair_index[name] = rows
        if sum(r.size for r in pair_index.values()) != pairs.a.size:
            raise ValueError("some pairs belong to no assignment block")
        same_student = sum(
            int(samples[i].student == samples[j].student)
            for _, s, e in blocks
            for i in range(s, e)
            for j in range(i + 1, e)
        )
        split = split or (samples[0].split if samples else "unknown")
        return cls(split, pairs, samples, tuple(blocks), pair_index, dict(exclusions or {}), same_student)

    @classmethod
    def from_manifest(
        cls, manifest: SplitManifest, split: str, *, limit_assignments: Optional[int] = None
    ) -> "EvalPairs":
        pairs = manifest.plagiarism_pairs(split)
        by_id = {s.id: s for s in manifest.samples(split, source="human")}
        assignments = None
        if limit_assignments is not None:
            assignments = set(sorted({by_id[i].assignment for i in pairs.ids})[:limit_assignments])
            pairs = restrict_pairs(pairs, sorted(assignments), [by_id[i].assignment for i in pairs.ids])
        return cls.build(pairs, by_id, split=split, exclusions=_exclusions(manifest, split, assignments))

    @property
    def assignments(self) -> np.ndarray:
        return self.pairs.assignment

    def view_mask(self, view: str) -> np.ndarray:
        if view == "all":
            return np.ones(self.pairs.a.size, dtype=bool)
        if view == "no_identical":
            hashes = np.array([s.norm_hash for s in self.samples], dtype=object)
            identical = hashes[self.pairs.a] == hashes[self.pairs.b]
            return ~(identical & (self.pairs.label == 0))
        raise ValueError(f"unknown view {view!r} (want one of {VIEWS})")

    def dropped(self, view: str) -> int:
        return int((~self.view_mask(view)).sum())


@dataclass(frozen=True)
class ScoredPairs:
    """Scores of every pair (all view; select a view with `EvalPairs.view_mask`) and MAP@R per
    view: `{value, n_queries, n_excluded, ap_sum, per_assignment}`."""

    scores: np.ndarray
    map_at_r: Dict[str, Dict]


def embedding_similarity(embeddings: np.ndarray) -> BlockSimilarity:
    """Cosine block similarity of row embeddings; all-zero rows (failed files) score 0."""
    emb = np.asarray(embeddings, dtype=np.float64)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    unit = np.divide(emb, norms, out=np.zeros_like(emb), where=norms > 0)

    def block(start: int, stop: int) -> np.ndarray:
        e = unit[start:stop]
        return e @ e.T

    return block


def stack_embeddings(entries: Sequence, pooling: str) -> Tuple[np.ndarray, int]:
    """`[n, H]` matrix of one pooling from `FileEmbedding`s; failed entries are zero rows (so they
    score 0 against everything). Returns the matrix and the number of failed entries."""
    dim = next((e.vectors[pooling].shape[0] for e in entries if e.success and pooling in e.vectors), 0)
    out = np.zeros((len(entries), dim), dtype=np.float32)
    failed = 0
    for i, e in enumerate(entries):
        if e.success and pooling in e.vectors:
            out[i] = e.vectors[pooling]
        else:
            failed += 1
    return out, failed


def score_pairs(similarity: BlockSimilarity, ep: EvalPairs, views: Sequence[str] = VIEWS) -> ScoredPairs:
    """Pair scores and per-view MAP@R from one block similarity matrix per assignment."""
    pairs = ep.pairs
    scores = np.zeros(pairs.a.size, dtype=np.float64)
    hashes = np.array([s.norm_hash for s in ep.samples], dtype=object)
    clusters = [s.cluster_id for s in ep.samples]
    per_view: Dict[str, Dict[str, Dict]] = {v: {} for v in views}
    for name, start, stop in ep.blocks:
        sim = np.array(similarity(start, stop), dtype=np.float64)
        rows = ep.pair_index[name]
        scores[rows] = sim[pairs.a[rows] - start, pairs.b[rows] - start]
        labels = clusters[start:stop]
        for view in views:
            s = sim
            if view == "no_identical":
                h = hashes[start:stop]
                index: Dict[str, int] = {}
                codes = np.array(
                    [-(i + 1) if c is None else index.setdefault(c, len(index)) for i, c in enumerate(labels)],
                    dtype=np.int64,
                )
                same_cluster = codes[:, None] == codes[None, :]
                drop = (h[:, None] == h[None, :]) & ~same_cluster
                np.fill_diagonal(drop, False)
                s = np.where(drop, -np.inf, sim)
            elif view != "all":
                raise ValueError(f"unknown view {view!r}")
            per_view[view][name] = M.map_at_r(s, labels)
    map_out = {}
    for view, per in per_view.items():
        agg = M.mean_map_at_r(per.values())
        map_out[view] = {**agg, "per_assignment": per}
    return ScoredPairs(scores, map_out)


def map_at_r_ci(
    per_assignment: Mapping[str, Mapping], *, n_boot: int, seed: int, alpha: float = 0.05
) -> Dict:
    """MAP@R with a grouped percentile bootstrap CI95 over assignments (design D11).

    Assignments are resampled with replacement in sorted order with `np.random.default_rng(seed)`,
    drawing like `metrics.bootstrap_many` with `groups`; each resample's MAP@R is the macro mean
    over its queries (`sum ap_sum / sum n_queries`). Resamples without queries are skipped."""
    units = sorted(per_assignment)
    ap = np.array([float(per_assignment[u]["ap_sum"]) for u in units])
    nq = np.array([int(per_assignment[u]["n_queries"]) for u in units])
    agg = M.mean_map_at_r(per_assignment[u] for u in units)
    out = {
        "value": agg["value"],
        "n_queries": agg["n_queries"],
        "n_excluded": agg["n_excluded"],
        "ap_sum": agg["ap_sum"],
        "reason": None if agg["value"] is not None else "no_queries",
        "ci95": None,
        "ci_reason": None,
        "n_boot": n_boot,
        "n_boot_valid": 0,
        "skipped_resamples": 0,
        "unit": "assignment",
        "n_units": len(units),
        "seed": seed,
        "alpha": alpha,
    }
    if agg["value"] is None or not units:
        return out
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n_boot):
        counts = np.bincount(rng.integers(0, len(units), len(units)), minlength=len(units))
        q = int((counts * nq).sum())
        if q:
            stats.append(float((counts * ap).sum() / q))
    out["n_boot_valid"] = len(stats)
    out["skipped_resamples"] = n_boot - len(stats)
    if len(stats) < max(1, n_boot // 2):
        out["ci_reason"] = "too_few_valid_resamples"
    else:
        lo, hi = np.quantile(np.asarray(stats), [alpha / 2, 1 - alpha / 2])
        out["ci95"] = [float(lo), float(hi)]
    return out
