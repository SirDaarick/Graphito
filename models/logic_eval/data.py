"""Data loaders for logic grouping evaluation (E1 and E2)."""

import gzip
import json
import os
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Union


def load_manifest_data(path: Union[str, Path]) -> Dict[str, Any]:
    """Load JSON or gzipped JSON manifest."""
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_e1_sample(
    manifest_path: Union[str, Path],
    max_per_block: int = 60,
    seed: int = 42,
    smoke_blocks: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Load human non-excluded sample for E1, 1 per dup_group, max N per assignment block.

    Args:
        manifest_path: Path to split_v1.json or split_v1.json.gz.
        max_per_block: Maximum number of files sampled per block.
        seed: Random seed for sampling.
        smoke_blocks: If set, limit total number of blocks (for --smoke mode).
    """
    data = load_manifest_data(manifest_path)
    entries = data.get("entries", [])

    # Filter human and non-excluded
    human_entries = [
        e for e in entries
        if e.get("source") == "human" and not e.get("excluded", False)
    ]

    # Exactly 1 file per dup_group
    by_dup_group: Dict[str, Dict[str, Any]] = {}
    for e in human_entries:
        dg = e.get("dup_group")
        if not dg:
            by_dup_group[e["id"]] = e
        elif dg not in by_dup_group:
            by_dup_group[dg] = e

    deduped_entries = list(by_dup_group.values())

    # Group by assignment block
    by_block: Dict[str, List[Dict[str, Any]]] = {}
    for e in deduped_entries:
        block = e.get("block") or e.get("assignment")
        by_block.setdefault(block, []).append(e)

    sorted_block_names = sorted(by_block.keys())
    if smoke_blocks is not None and smoke_blocks > 0:
        sorted_block_names = sorted_block_names[:smoke_blocks]

    rng = random.Random(seed)
    sampled_entries: List[Dict[str, Any]] = []

    for block_name in sorted_block_names:
        block_items = sorted(by_block[block_name], key=lambda x: x["id"])
        if len(block_items) > max_per_block:
            chosen = rng.sample(block_items, max_per_block)
        else:
            chosen = block_items
        sampled_entries.extend(chosen)

    return sampled_entries


def load_e2_stats(
    entries: List[Dict[str, Any]],
    stats_dir: Union[str, Path] = "data/raw/stats",
    min_pass: int = 5,
    min_fail: int = 3,
    seed: int = 42,
) -> Dict[str, List[Dict[str, Any]]]:
    """Match entries with student stats, extracting valid last_test_results.

    1. Resolves multiple files per (course, student, assignment) keeping exactly 1
       (prioritizing files with main or largest size).
    2. Deduplicates per dup_group within each assignment:
       - If all items in dup_group have identical last_test_results, keep 1 (deterministic by seed).
       - If items in dup_group have conflicting last_test_results, discard entire dup_group.
    3. Filters assignments with at least min_pass passing solutions and min_fail failing solutions.

    Returns mapping of qualifying assignment -> list of enriched entry dicts.
    """
    stats_dir = Path(stats_dir)
    enriched_by_assignment: Dict[str, List[Dict[str, Any]]] = {}

    # Step 1: Group by (course, student, assignment) to ensure 1 file per student per assignment
    student_assign_map: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for e in entries:
        course = e.get("course")
        student = e.get("student")
        assignment = e.get("assignment")
        if course and student and assignment:
            key = (str(course), str(student), str(assignment))
            student_assign_map.setdefault(key, []).append(e)

    resolved_entries: List[Dict[str, Any]] = []
    for key, cand_list in student_assign_map.items():
        if len(cand_list) == 1:
            resolved_entries.append(cand_list[0])
        else:
            # Deterministic resolution: pick candidate with main, else highest n_tokens/size, else smallest id
            def _rank_cand(item: Dict[str, Any]) -> Tuple[int, int, str]:
                is_main = 1 if "main" in str(item.get("id", "")).lower() else 0
                n_tokens = item.get("n_tokens") or 0
                return (is_main, n_tokens, str(item.get("id", "")))

            chosen = max(cand_list, key=_rank_cand)
            resolved_entries.append(chosen)

    # Match with student stats
    for e in resolved_entries:
        course = e.get("course")
        student = e.get("student")
        assignment = e.get("assignment")
        s_str = str(student)
        cand_files = [f"{s_str}.json"]
        if not s_str.startswith("student"):
            cand_files.append(f"student{s_str}.json")

        stats_path = None
        for cf in cand_files:
            cp = stats_dir / course / cf
            if cp.is_file():
                stats_path = cp
                break

        if not stats_path:
            continue

        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                student_data = json.load(f)
            if not isinstance(student_data, dict):
                continue
            assign_data = student_data.get(assignment)
            if not isinstance(assign_data, dict):
                continue

            ltr = assign_data.get("last_test_results", "")
            if not ltr or "/" not in ltr:
                continue

            parts = ltr.split("/")
            if len(parts) != 2:
                continue
            x, y = int(parts[0]), int(parts[1])
            if y <= 0:
                continue

            pass_rate = x / y
            pasa = (x == y)

            enriched = dict(e)
            enriched["last_test_results"] = ltr
            enriched["pass_rate"] = pass_rate
            enriched["pasa"] = pasa
            enriched["passed_tests"] = x
            enriched["total_tests"] = y
            enriched_by_assignment.setdefault(assignment, []).append(enriched)
        except Exception:
            continue

    # Step 2: Deduplicate within each assignment by dup_group
    import random
    rng = random.Random(seed)

    deduped_by_assignment: Dict[str, List[Dict[str, Any]]] = {}
    for assign, items in enriched_by_assignment.items():
        dg_map: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            dg = item.get("dup_group") or item.get("id")
            dg_map.setdefault(dg, []).append(item)

        assignment_clean: List[Dict[str, Any]] = []
        for dg, dg_items in dg_map.items():
            if len(dg_items) == 1:
                assignment_clean.append(dg_items[0])
            else:
                # Multiple submissions in same dup_group within this assignment
                distinct_ltrs = set(x["last_test_results"] for x in dg_items)
                if len(distinct_ltrs) == 1:
                    # Consistent results: keep exactly 1 deterministically
                    sorted_items = sorted(dg_items, key=lambda x: str(x.get("id")))
                    chosen = rng.choice(sorted_items)
                    assignment_clean.append(chosen)
                else:
                    # Inconsistent results: discard the entire dup_group as noisy ground truth
                    continue

        deduped_by_assignment[assign] = assignment_clean

    # Step 3: Filter assignments by min_pass and min_fail
    qualified: Dict[str, List[Dict[str, Any]]] = {}
    for assign, items in deduped_by_assignment.items():
        n_p = sum(1 for item in items if item["pasa"])
        n_f = sum(1 for item in items if not item["pasa"])
        if n_p >= min_pass and n_f >= min_fail:
            qualified[assign] = items

    return qualified

