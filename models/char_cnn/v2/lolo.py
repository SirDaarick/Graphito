"""Leave-one-LLM-out helpers for CharCNN v2 (pure functions over manifest samples or dicts).

- `restrict_ai_models`: keep only AI entries of the allowed generators in the listed splits
  (train and val by default); humans and every other split are untouched.
- `count_ai_groups`: unique `dup_group` count of one generator in one split.
- `match_ai_groups`: subsample train AI by `dup_group`, stratified by `assignment` (largest-remainder
  quotas), to an exact number of groups; deterministic given the seed.
- `partition_by_generator`: split entries into `human` and one bucket per AI generator.
"""

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from models.evaluation.seed import stable_rng

__all__ = ["restrict_ai_models", "count_ai_groups", "match_ai_groups", "partition_by_generator"]

HUMAN = "human"


def _get(entry: Any, name: str, default: Any = None) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _is_ai(entry: Any) -> bool:
    return _get(entry, "source") != HUMAN


def _group_key(entry: Any) -> str:
    grp = _get(entry, "dup_group")
    return str(grp) if grp is not None else f"single:{_get(entry, 'id')}"


def restrict_ai_models(
    entries: Sequence[Any], allowed_models: Iterable[str], splits: Sequence[str] = ("train", "val")
) -> List[Any]:
    """Drop AI entries of `splits` whose `model` is not allowed; keep everything else, in order."""
    allowed: Set[str] = set(allowed_models)
    if not allowed:
        raise ValueError("allowed_models must not be empty")
    scoped = set(splits)
    return [
        e for e in entries
        if not _is_ai(e) or _get(e, "split") not in scoped or _get(e, "model") in allowed
    ]


def count_ai_groups(entries: Sequence[Any], model: str, split: str) -> int:
    """Unique dup_groups of the AI entries of `model` in `split`."""
    return len({_group_key(e) for e in entries if _is_ai(e) and _get(e, "model") == model and _get(e, "split") == split})


def _quotas(sizes: Mapping[str, int], target: int) -> Dict[str, int]:
    """Largest-remainder allocation of `target` over strata proportional to `sizes` (ties by name)."""
    total = sum(sizes.values())
    base = {k: (target * n) // total for k, n in sizes.items()}
    left = target - sum(base.values())
    order = sorted(sizes, key=lambda k: (-((target * sizes[k]) % total), k))
    for k in order[:left]:
        base[k] += 1
    return base


def match_ai_groups(entries: Sequence[Any], target_groups: int, seed: int, split: str = "train") -> List[Any]:
    """Keep exactly `target_groups` AI dup_groups of `split` (whole groups, stratified by assignment)."""
    groups: Dict[str, str] = {}
    for e in entries:
        if _is_ai(e) and _get(e, "split") == split:
            task = str(_get(e, "assignment") if _get(e, "assignment") is not None else "default")
            key = _group_key(e)
            groups[key] = min(groups.get(key, task), task)
    if target_groups < 1 or target_groups > len(groups):
        raise ValueError(f"target_groups must be in [1, {len(groups)}] (got {target_groups})")

    by_task: Dict[str, List[str]] = defaultdict(list)
    for key, task in groups.items():
        by_task[task].append(key)
    quotas = _quotas({t: len(g) for t, g in by_task.items()}, target_groups)

    chosen: Set[str] = set()
    for task in sorted(by_task):
        perm = sorted(by_task[task])
        stable_rng(seed, f"lolo_match:{task}").shuffle(perm)
        chosen.update(perm[: quotas[task]])
    return [
        e for e in entries
        if not (_is_ai(e) and _get(e, "split") == split) or _group_key(e) in chosen
    ]


def partition_by_generator(entries: Sequence[Any]) -> Dict[str, List[Any]]:
    """`{"human": [...], "<model>": [...]}`, preserving order within each bucket."""
    parts: Dict[str, List[Any]] = defaultdict(list)
    for e in entries:
        parts[HUMAN if not _is_ai(e) else str(_get(e, "model"))].append(e)
    return dict(parts)
