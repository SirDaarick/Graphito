"""AI training data subsampling for CharCNN v2 learning curve analysis.

Provides `subsample_ai_train(entries, fraction, seed)`:
- Subsets entries by `dup_group` to guarantee duplicate files are never split.
- Stratified by task (`assignment`): each fraction preserves the proportion of tasks
  and retains at least one group per task for fraction > 0.
- Nested prefixes by seed: with the same seed, subset(f1) <= subset(f2) for f1 <= f2.
- Intact non-target entries: human samples, validation samples, and test samples are
  always kept 100% untouched.
- Deterministic: derives permutations via `stable_rng(seed, ...)` independently of
  global state.
- Supports both `Sequence[Sample]` / `Sequence[dict]` and `EncodedSet`.
"""

import math
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Sequence, Set, TypeVar, Union

from models.char_cnn.v2.data import EncodedSet
from models.evaluation.seed import stable_rng

T = TypeVar("T")


def _get_field(entry: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(field_name, default)
    return getattr(entry, field_name, default)


def _is_train_ai(entry: Any) -> bool:
    source = _get_field(entry, "source")
    split = _get_field(entry, "split")
    if source == "human":
        return False
    if split in ("val", "test"):
        return False
    return True


def subsample_ai_train(
    entries: Union[Sequence[T], EncodedSet],
    fraction: float,
    seed: int,
) -> Union[List[T], EncodedSet]:
    """Subset the AI train samples in `entries` by `dup_group`, stratified by task and nested by seed.

    Args:
        entries: A Sequence of Sample/dict items, or an EncodedSet.
        fraction: Fraction of AI train data to keep, in (0.0, 1.0].
        seed: Random seed for deterministic group permutation.

    Returns:
        Filtered entries of the same type as input (List or EncodedSet), preserving
        original relative ordering. Non-train-AI entries are preserved intact.
    """
    if not (isinstance(fraction, (int, float)) and math.isfinite(fraction) and 0.0 <= fraction <= 1.0):
        raise ValueError(f"fraction must be a finite float in [0.0, 1.0], got {fraction!r}")

    if fraction == 1.0:
        return entries

    is_encoded_set = isinstance(entries, EncodedSet)
    sample_list: Sequence[Any] = entries.samples if is_encoded_set else entries

    if not sample_list:
        return entries

    # Identify eligible AI train entries
    eligible_indices: List[int] = []
    for idx, item in enumerate(sample_list):
        if _is_train_ai(item):
            eligible_indices.append(idx)

    if not eligible_indices or fraction == 0.0 and len(eligible_indices) == 0:
        return entries

    # Map each dup_group to its entries and task
    group_to_indices: Dict[str, List[int]] = defaultdict(list)
    group_to_task: Dict[str, str] = {}

    for idx in eligible_indices:
        item = sample_list[idx]
        dup_grp = _get_field(item, "dup_group")
        item_id = str(_get_field(item, "id", f"idx_{idx}"))
        group_key = str(dup_grp) if dup_grp is not None else f"single:{item_id}"
        group_to_indices[group_key].append(idx)

        task = _get_field(item, "assignment")
        task_key = str(task) if task is not None else "default"
        if group_key not in group_to_task:
            group_to_task[group_key] = task_key
        else:
            # Deterministic tie-breaker in the rare case of cross-task dup_group
            group_to_task[group_key] = min(group_to_task[group_key], task_key)

    # Collect groups by task
    task_to_groups: Dict[str, List[str]] = defaultdict(list)
    for group_key, task_key in group_to_task.items():
        task_to_groups[task_key].append(group_key)

    # For each task, shuffle groups deterministically and take prefix
    selected_groups: Set[str] = set()
    for task_key in sorted(task_to_groups.keys()):
        groups = sorted(task_to_groups[task_key])
        n_groups = len(groups)
        if n_groups == 0:
            continue

        rng = stable_rng(seed, f"subsample_ai:{task_key}")
        perm = list(groups)
        rng.shuffle(perm)

        # Stratified rounding: retain at least 1 group per task when fraction > 0
        if fraction <= 0.0:
            k = 0
        else:
            k = min(n_groups, max(1, int(round(n_groups * fraction))))

        selected_groups.update(perm[:k])

    # Filter while preserving original relative order
    keep_mask = [True] * len(sample_list)
    for idx in eligible_indices:
        item = sample_list[idx]
        dup_grp = _get_field(item, "dup_group")
        item_id = str(_get_field(item, "id", f"idx_{idx}"))
        group_key = str(dup_grp) if dup_grp is not None else f"single:{item_id}"
        if group_key not in selected_groups:
            keep_mask[idx] = False

    kept_indices = [i for i, keep in enumerate(keep_mask) if keep]

    if is_encoded_set:
        sub_samples = [entries.samples[i] for i in kept_indices]
        sub_arrays = [entries.arrays[i] for i in kept_indices]
        return EncodedSet.build(sub_samples, sub_arrays)

    return [sample_list[i] for i in kept_indices]
