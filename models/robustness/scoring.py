"""Cross-file similarity functions and paired bootstrap evaluation for robustness."""

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
import numpy as np
from scipy import sparse

from models.evaluation import metrics as M
from models.graphcodebert.v2.pairs import BlockSimilarity


class CrossSetSimilarity:
    """Block Jaccard of per-file hash sets between original and transformed sets:
    |A∩B| / |A∪B| from two sparse incidence matrices: inter = inc_o @ inc_t.T.
    Matches SetSimilarity when orig_sets == trans_sets.
    """

    def __init__(self, orig_sets: Sequence[np.ndarray], trans_sets: Sequence[np.ndarray]):
        if len(orig_sets) != len(trans_sets):
            raise ValueError(f"orig_sets and trans_sets must have same length ({len(orig_sets)} vs {len(trans_sets)})")
        self.orig_sets = [np.asarray(s) for s in orig_sets]
        self.trans_sets = [np.asarray(s) for s in trans_sets]

    def __call__(self, start: int, stop: int) -> np.ndarray:
        block_o = self.orig_sets[start:stop]
        block_t = self.trans_sets[start:stop]
        n = len(block_o)
        sizes_o = np.array([s.size for s in block_o], dtype=np.float64)
        sizes_t = np.array([s.size for s in block_t], dtype=np.float64)
        if n == 0 or sizes_o.sum() == 0 or sizes_t.sum() == 0:
            return np.zeros((n, n), dtype=np.float64)

        vals_o = np.concatenate(block_o)
        vals_t = np.concatenate(block_t)
        all_vals = np.concatenate([vals_o, vals_t])
        _, cols = np.unique(all_vals, return_inverse=True)
        cols_o = cols[:vals_o.size]
        cols_t = cols[vals_o.size:]
        num_cols = int(cols.max()) + 1

        rows_o = np.repeat(np.arange(n), sizes_o.astype(np.int64))
        rows_t = np.repeat(np.arange(n), sizes_t.astype(np.int64))
        inc_o = sparse.csr_matrix((np.ones(cols_o.size), (rows_o, cols_o)), shape=(n, num_cols))
        inc_t = sparse.csr_matrix((np.ones(cols_t.size), (rows_t, cols_t)), shape=(n, num_cols))

        inter = (inc_o @ inc_t.T).toarray()
        union = sizes_o[:, None] + sizes_t[None, :] - inter
        return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


def cross_embedding_similarity(E_orig: np.ndarray, E_trans: np.ndarray) -> BlockSimilarity:
    """Cosine block similarity between original and transformed row embeddings: unit_o @ unit_t.T."""
    emb_o = np.asarray(E_orig, dtype=np.float64)
    emb_t = np.asarray(E_trans, dtype=np.float64)
    if emb_o.shape != emb_t.shape:
        raise ValueError(f"E_orig and E_trans shapes differ: {emb_o.shape} vs {emb_t.shape}")

    norms_o = np.linalg.norm(emb_o, axis=1, keepdims=True)
    norms_t = np.linalg.norm(emb_t, axis=1, keepdims=True)
    unit_o = np.divide(emb_o, norms_o, out=np.zeros_like(emb_o), where=norms_o > 0)
    unit_t = np.divide(emb_t, norms_t, out=np.zeros_like(emb_t), where=norms_t > 0)

    def block(start: int, stop: int) -> np.ndarray:
        eo = unit_o[start:stop]
        et = unit_t[start:stop]
        return eo @ et.T

    return block


def _parse_scores_dict(
    scores_dict: Mapping[Any, Any],
) -> Dict[Tuple[str, str], np.ndarray]:
    """Normalize various dictionary structures to a uniform {(method, cond): scores_array}."""
    flat: Dict[Tuple[str, str], np.ndarray] = {}
    for k, v in scores_dict.items():
        if isinstance(v, Mapping):
            # Nested: {method: {cond: scores}}
            method = str(k)
            for cond, s in v.items():
                flat[(method, str(cond))] = np.asarray(s, dtype=np.float64)
        elif isinstance(k, tuple) and len(k) == 2:
            flat[(str(k[0]), str(k[1]))] = np.asarray(v, dtype=np.float64)
        elif isinstance(k, str):
            if "__" in k:
                parts = k.split("__", 1)
                flat[(parts[0], parts[1])] = np.asarray(v, dtype=np.float64)
            elif ":" in k:
                parts = k.split(":", 1)
                flat[(parts[0], parts[1])] = np.asarray(v, dtype=np.float64)
            else:
                flat[("score", k)] = np.asarray(v, dtype=np.float64)
        else:
            flat[(str(k), "default")] = np.asarray(v, dtype=np.float64)
    return flat


import concurrent.futures
import math
import os


def _eval_recipe(recipe: Tuple[Any, ...], col_aucs: Sequence[Optional[float]]) -> Optional[float]:
    rtype = recipe[0]
    if rtype == "auc":
        val = col_aucs[recipe[1]]
        return float(val) if val is not None and math.isfinite(val) else None
    elif rtype == "delta":
        v_t = col_aucs[recipe[1]]
        v_b = col_aucs[recipe[2]]
        if v_t is not None and math.isfinite(v_t) and v_b is not None and math.isfinite(v_b):
            return float(v_t - v_b)
        return None
    elif rtype == "did":
        v_ak = col_aucs[recipe[1]]
        v_a0 = col_aucs[recipe[2]]
        v_bk = col_aucs[recipe[3]]
        v_b0 = col_aucs[recipe[4]]
        if (
            v_ak is not None and math.isfinite(v_ak)
            and v_a0 is not None and math.isfinite(v_a0)
            and v_bk is not None and math.isfinite(v_bk)
            and v_b0 is not None and math.isfinite(v_b0)
        ):
            return float((v_ak - v_a0) - (v_bk - v_b0))
        return None
    return None


def _fast_roc_auc(y: np.ndarray, s: np.ndarray) -> Optional[float]:
    """Exact Mann-Whitney U rank statistic with midranks for ties.
    Optimized for fast bootstrap resampling without redundant array allocations.
    """
    n_pos = np.sum(y)
    n_neg = len(y) - n_pos
    if n_pos <= 0 or n_neg <= 0:
        return None
    order = np.argsort(s)
    s_sorted = s[order]
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1)
    dup_mask = np.diff(s_sorted) == 0
    if np.any(dup_mask):
        starts = np.r_[0, np.flatnonzero(np.diff(s_sorted)) + 1]
        ends = np.r_[starts[1:], len(s)]
        counts = ends - starts
        for start, end in zip(starts[counts > 1], ends[counts > 1]):
            ranks[order[start:end]] = (start + 1 + end) / 2.0
    sum_ranks_pos = np.sum(ranks[y == 1])
    u = sum_ranks_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def _resample_chunk(
    chunk_seed: int,
    n_chunk: int,
    y_data: Any,
    s_data: Any,
    n: int,
    num_cols: int,
    recipes: Mapping[str, Tuple[Any, ...]],
    groups_data: Optional[Tuple[np.ndarray, np.ndarray, int]],
) -> Tuple[Dict[str, List[float]], Dict[str, int]]:
    if isinstance(y_data, str):
        y_arr = np.memmap(y_data, dtype=np.int64, mode="r", shape=(n,))
    else:
        y_arr = y_data
    if isinstance(s_data, str):
        S = np.memmap(s_data, dtype=np.float64, mode="r", shape=(n, num_cols))
    else:
        S = s_data

    rng = np.random.default_rng(chunk_seed)
    stats: Dict[str, List[float]] = {name: [] for name in recipes}
    skipped: Dict[str, int] = {name: 0 for name in recipes}

    for _ in range(n_chunk if n else 0):
        if groups_data is None:
            idx = rng.integers(0, n, n)
        else:
            by_group, group_of_sorted, n_units = groups_data
            counts = np.bincount(rng.integers(0, n_units, n_units), minlength=n_units)
            idx = np.repeat(by_group, counts[group_of_sorted])

        yy = y_arr[idx]
        # Evaluate each column individually without allocating the 608 MB matrix S[idx]
        col_aucs = [_fast_roc_auc(yy, S[:, k][idx]) for k in range(num_cols)]

        for name, recipe in recipes.items():
            val = _eval_recipe(recipe, col_aucs)
            if val is not None:
                stats[name].append(val)
            else:
                skipped[name] += 1

    return stats, skipped


def _bootstrap_counts(n_units: int, n_boot: int, seed: int) -> np.ndarray:
    """`[n_boot, n_units]` how many times each group is drawn in each resample: the same draws, in the
    same chunks and with the same seeds, as `_resample_chunk` makes for `paired_bootstrap`."""
    workers = min(4, os.cpu_count() or 4) if n_boot >= 100 else 1
    if workers > 1:
        sizes = [n_boot // workers] * workers
        for i in range(n_boot % workers):
            sizes[i] += 1
        plan = [(seed + i * 10007, size) for i, size in enumerate(sizes) if size > 0]
    else:
        plan = [(seed, n_boot)]
    rows = []
    for chunk_seed, n_chunk in plan:
        rng = np.random.default_rng(chunk_seed)
        for _ in range(n_chunk):
            rows.append(np.bincount(rng.integers(0, n_units, n_units), minlength=n_units))
    return np.asarray(rows, dtype=np.float64).reshape(-1, n_units)


def _group_auc_table(y: np.ndarray, s: np.ndarray, codes: np.ndarray, n_units: int):
    """One sort per score column. For every positive: the number of negatives of each group strictly
    below its score plus half of those tied with it. A resample that draws group g `c_g` times turns
    these counts into its exact midrank AUC (see `_grouped_aucs`)."""
    order = np.argsort(s, kind="stable")
    s_sorted, y_sorted, g_sorted = s[order], y[order], codes[order]
    n = s.size
    pos_idx = np.flatnonzero(y_sorted == 1)
    if pos_idx.size == 0:
        return None
    starts = np.r_[0, np.flatnonzero(np.diff(s_sorted)) + 1]
    ends = np.r_[starts[1:], n]
    block_of = np.repeat(np.arange(starts.size), ends - starts)[pos_idx]
    lo, hi = starts[block_of], ends[block_of]
    neg = y_sorted == 0
    half_tied_below = np.empty((pos_idx.size, n_units), dtype=np.float64)
    for g in range(n_units):
        cum = np.concatenate(([0], np.cumsum(neg & (g_sorted == g))))
        half_tied_below[:, g] = cum[lo] + 0.5 * (cum[hi] - cum[lo])
    n_pos = np.bincount(codes[y == 1], minlength=n_units).astype(np.float64)
    n_neg = np.bincount(codes[y == 0], minlength=n_units).astype(np.float64)
    return g_sorted[pos_idx], half_tied_below, n_pos, n_neg


def _grouped_aucs(table, counts: np.ndarray) -> np.ndarray:
    """AUC of every resample (rows of `counts`), NaN where it has no positive or no negative."""
    pos_group, score, n_pos, n_neg = table
    w_pos, w_neg = counts @ n_pos, counts @ n_neg
    numerator = (counts[:, pos_group].T * (score @ counts.T)).sum(axis=0)
    out = np.full(counts.shape[0], np.nan)
    ok = (w_pos > 0) & (w_neg > 0)
    out[ok] = numerator[ok] / (w_pos[ok] * w_neg[ok])
    return out


def _grouped_fast_stats(y, S, codes, n_units, recipes, n_boot, seed):
    counts = _bootstrap_counts(n_units, n_boot, seed)
    aucs = np.full((S.shape[1], counts.shape[0]), np.nan)
    for k in range(S.shape[1]):
        table = _group_auc_table(y, S[:, k], codes, n_units)
        if table is not None:
            aucs[k] = _grouped_aucs(table, counts)
    stats: Dict[str, List[float]] = {name: [] for name in recipes}
    skipped: Dict[str, int] = {name: 0 for name in recipes}
    for b in range(counts.shape[0]):
        col_aucs = [None if math.isnan(v) else float(v) for v in aucs[:, b]]
        for name, recipe in recipes.items():
            val = _eval_recipe(recipe, col_aucs)
            if val is not None:
                stats[name].append(val)
            else:
                skipped[name] += 1
    return stats, skipped


def paired_bootstrap(
    y: Sequence[int],
    scores_dict: Mapping[Any, Any],
    groups: Optional[Sequence[Any]] = None,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
    contrasts: Optional[Mapping[str, Tuple[str, str, str]]] = None,
    min_valid: Optional[int] = None,
    fast_grouped: bool = False,
) -> Dict[str, Dict]:
    """Compute paired percentile bootstrap CIs for delta vs T0 and DiD between methods.

    Evaluates column ROC-AUCs once per resample, deriving all individual AUCs,
    deltas against T0, and DiD contrasts by simple subtraction. This achieves
    exact mathematical equivalence to independent resampling while eliminating
    redundant sorting of score arrays.

    Args:
        y: Ground truth binary labels.
        scores_dict: Mapping of method and condition to 1D score arrays. Can be:
                     {method: {cond: scores}}, {(method, cond): scores}, or {"method__cond": scores}.
        groups: Optional cluster or assignment identifiers for grouped resampling.
        n_boot: Number of bootstrap draws.
        seed: Random seed.
        alpha: Significance level for two-tailed (1 - alpha) CI.
        contrasts: Optional explicit mapping of contrast_name -> (cond, method_a, method_b).
        min_valid: Minimum number of valid resamples required to compute CI.
    """
    if fast_grouped and groups is None:
        raise ValueError("fast_grouped requires groups (the grouped bootstrap is what it accelerates)")
    flat = _parse_scores_dict(scores_dict)
    if not flat:
        return {}

    items = list(flat.items())
    col_names = [k for k, _ in items]
    cols = [v for _, v in items]
    col_map = {name: i for i, name in enumerate(col_names)}

    S = np.column_stack(cols)
    num_cols = S.shape[1]
    methods = sorted({m for m, _ in col_names})
    conditions = sorted({c for _, c in col_names})

    # Build metric recipes: each metric maps to a tuple:
    # ("auc", col_idx)
    # ("delta", target_col_idx, base_col_idx)
    # ("did", a_target_idx, a_base_idx, b_target_idx, b_base_idx)
    recipes: Dict[str, Tuple[Any, ...]] = {}

    # 1. Individual AUCs
    for (m, c), idx in col_map.items():
        recipes[f"auc__{m}__{c}"] = ("auc", idx)

    # 2. Deltas against T0 for each method
    for m in methods:
        if (m, "T0") in col_map:
            base_col = col_map[(m, "T0")]
            for c in conditions:
                if c != "T0" and (m, c) in col_map:
                    target_col = col_map[(m, c)]
                    recipes[f"delta__{m}__{c}"] = ("delta", target_col, base_col)

    # 3. Difference-in-differences (DiD) between pairs of methods for condition c
    # DiD(Tk; A, B) = [AUC_A(Tk) - AUC_A(T0)] - [AUC_B(Tk) - AUC_B(T0)]
    if contrasts is not None:
        for name, (c, m1, m2) in contrasts.items():
            if (m1, "T0") in col_map and (m1, c) in col_map and (m2, "T0") in col_map and (m2, c) in col_map:
                a0, ak = col_map[(m1, "T0")], col_map[(m1, c)]
                b0, bk = col_map[(m2, "T0")], col_map[(m2, c)]
                recipes[name] = ("did", ak, a0, bk, b0)
    else:
        for i, m1 in enumerate(methods):
            for m2 in methods[i + 1:]:
                if (m1, "T0") in col_map and (m2, "T0") in col_map:
                    a0, b0 = col_map[(m1, "T0")], col_map[(m2, "T0")]
                    for c in conditions:
                        if c != "T0" and (m1, c) in col_map and (m2, c) in col_map:
                            ak, bk = col_map[(m1, c)], col_map[(m2, c)]
                            recipes[f"did__{c}__{m1}__{m2}"] = ("did", ak, a0, bk, b0)

    y_arr = np.asarray(y)
    n = y_arr.shape[0]
    if S.shape[0] != n:
        raise ValueError(f"labels and scores differ in length: {y_arr.shape} vs {S.shape}")
    if min_valid is None:
        min_valid = max(1, n_boot // 2)

    rng = np.random.default_rng(seed)
    if groups is None:
        unit, n_units = "sample", n
    else:
        groups_arr = np.asarray(groups, dtype=object)
        if groups_arr.shape[0] != n:
            raise ValueError(f"labels and groups differ in length: {n} vs {groups_arr.shape[0]}")
        _, codes = np.unique(groups_arr.astype(str), return_inverse=True)
        by_group = np.argsort(codes, kind="stable")
        group_of_sorted = codes[by_group]
        unit, n_units = "group", int(codes.max()) + 1 if n else 0

    stats: Dict[str, List[float]] = {name: [] for name in recipes}
    skipped: Dict[str, int] = {name: 0 for name in recipes}
    groups_data = (by_group, group_of_sorted, n_units) if groups is not None else None

    workers = min(4, os.cpu_count() or 4) if n_boot >= 100 else 1
    if fast_grouped:
        # Same resamples and same AUC as the branches below, from one sort per column (exact, much faster).
        stats, skipped = _grouped_fast_stats(y_arr, S, codes, n_units, recipes, n_boot, seed) if n else (stats, skipped)
    elif workers > 1:
        chunk_size = n_boot // workers
        chunks = [chunk_size] * workers
        remainder = n_boot % workers
        for r_i in range(remainder):
            chunks[r_i] += 1

        import tempfile
        import uuid
        temp_dir = tempfile.gettempdir()
        uid = uuid.uuid4().hex[:8]
        y_path = os.path.join(temp_dir, f"_boot_y_{uid}.dat")
        s_path = os.path.join(temp_dir, f"_boot_s_{uid}.dat")

        try:
            mm_y = np.memmap(y_path, dtype=np.int64, mode="w+", shape=(n,))
            mm_y[:] = y_arr[:]
            mm_y.flush()
            del mm_y

            mm_s = np.memmap(s_path, dtype=np.float64, mode="w+", shape=(n, num_cols))
            mm_s[:] = S[:]
            mm_s.flush()
            del mm_s

            tasks = [
                (seed + i * 10007, ch, y_path, s_path, n, num_cols, recipes, groups_data)
                for i, ch in enumerate(chunks) if ch > 0
            ]
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_resample_chunk, *t) for t in tasks]
                for fut in concurrent.futures.as_completed(futures):
                    c_stats, c_skipped = fut.result()
                    for name in recipes:
                        stats[name].extend(c_stats[name])
                        skipped[name] += c_skipped[name]
        finally:
            if os.path.isfile(y_path):
                try:
                    os.remove(y_path)
                except OSError:
                    pass
            if os.path.isfile(s_path):
                try:
                    os.remove(s_path)
                except OSError:
                    pass
    else:
        c_stats, c_skipped = _resample_chunk(
            seed, n_boot, y_arr, S, n, num_cols, recipes, groups_data
        )
        for name in recipes:
            stats[name].extend(c_stats[name])
            skipped[name] += c_skipped[name]

    # Point estimates
    point_col_aucs = [_fast_roc_auc(y_arr, S[:, k]) for k in range(num_cols)] if n else [None] * num_cols

    out = {}
    for name, recipe in recipes.items():
        point = _eval_recipe(recipe, point_col_aucs)
        result = {
            "value": float(point) if point is not None else None,
            "reason": None,
            "lo": None,
            "hi": None,
            "ci95": None,
            "alpha": alpha,
            "n_boot": n_boot,
            "n_valid": len(stats[name]),
            "skipped_resamples": skipped[name],
            "unit": unit,
            "n_units": n_units,
            "seed": seed,
        }
        if result["value"] is None:
            try:
                result["reason"] = M.undefined_reason(y_arr) or "undefined"
            except ValueError:
                result["reason"] = "undefined"
        elif len(stats[name]) < min_valid:
            result["reason"] = "too_few_valid_resamples"
        else:
            lo, hi = np.quantile(np.asarray(stats[name]), [alpha / 2, 1 - alpha / 2])
            result.update(lo=float(lo), hi=float(hi), ci95=[float(lo), float(hi)])
        out[name] = result

    return out


NORMALIZED_METHODS = ("v2_norm",)
# Methods named `ft_<name>` score a LoRA adapter (models.graphcodebert.v2.adapter) on the canonicalized text,
# like v2_norm: the adapters were trained on `v2_norm` inputs.
ADAPTER_PREFIX = "ft_"
_CANON_MEMO: Dict[Tuple[str, str], str] = {}


def _canonical(text: str, lang: str) -> str:
    """canonicalize_code with a per-process memo (identical text and language give identical output)."""
    key = (lang, text)
    hit = _CANON_MEMO.get(key)
    if hit is None:
        from models.logic_eval.canonical import canonicalize_code

        hit = _CANON_MEMO[key] = canonicalize_code(text, lang)
    return hit


def texts_for_method(
    method: str,
    orig_texts: Sequence[str],
    trans_texts: Sequence[str],
    langs: Sequence[str],
) -> Tuple[List[str], List[str]]:
    """Texts to embed for ``method``. ``v2_norm`` canonicalizes identifiers on BOTH sides, after
    the transform; every other method gets the texts unchanged."""
    if not (len(orig_texts) == len(trans_texts) == len(langs)):
        raise ValueError("orig_texts, trans_texts and langs must have the same length")
    if method not in NORMALIZED_METHODS and not method.startswith(ADAPTER_PREFIX):
        return list(orig_texts), list(trans_texts)
    return (
        [_canonical(t, l) for t, l in zip(orig_texts, langs)],
        [_canonical(t, l) for t, l in zip(trans_texts, langs)],
    )