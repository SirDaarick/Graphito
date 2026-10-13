"""Tests for evaluation metrics and data loaders in models.logic_eval."""

import json
import numpy as np
import pytest


def test_e1_map_at_r_perfect_and_random():
    from models.logic_eval.grouping import compute_map_at_r, compute_recall_at_1, random_baseline_map_at_r

    # 3 clusters of 4 elements each (12 items total)
    labels = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    # Perfect similarity matrix: 1.0 within cluster, 0.0 across clusters
    sim = np.zeros((12, 12))
    for i in range(12):
        for j in range(12):
            if labels[i] == labels[j]:
                sim[i, j] = 1.0
            else:
                sim[i, j] = 0.0

    res = compute_map_at_r(sim, labels)
    assert res["value"] == pytest.approx(1.0)
    assert res["n_queries"] == 12

    rec1 = compute_recall_at_1(sim, labels)
    assert rec1 == pytest.approx(1.0)

    # Random baseline should be well below 1.0 (approx (R-1)/(N-1) = 3/11 ~ 0.27)
    rnd = random_baseline_map_at_r(labels, seed=42, n_permutations=100)
    assert 0.1 <= rnd < 0.6


def test_e1_silhouette_and_auc():
    from models.logic_eval.grouping import compute_cosine_silhouette, compute_pairwise_roc_auc

    # 2 clusters well separated
    labels = ["A"] * 5 + ["B"] * 5
    sim = np.zeros((10, 10))
    for i in range(10):
        for j in range(10):
            if labels[i] == labels[j]:
                sim[i, j] = 0.95
            else:
                sim[i, j] = 0.05

    sil = compute_cosine_silhouette(sim, labels)
    assert sil > 0.8

    auc = compute_pairwise_roc_auc(sim, labels)
    assert auc == pytest.approx(1.0)


def test_e2_leave_one_out_reference_evaluation():
    from models.logic_eval.correctness import evaluate_assignment_leave_one_out

    # 5 passing solutions (indices 0..4) and 3 failing solutions (indices 5..7)
    pass_rates = [1.0] * 5 + [0.5, 0.2, 0.0]
    n = 8
    # Passing solutions are close to each other (sim 0.9), but far from failing (sim 0.2)
    sim = np.full((n, n), 0.2)
    np.fill_diagonal(sim, 1.0)
    for i in range(5):
        for j in range(5):
            sim[i, j] = 0.9

    res = evaluate_assignment_leave_one_out(sim, pass_rates)
    assert res["n_pass"] == 5
    assert res["n_fail"] == 3
    assert res["auc"] == pytest.approx(1.0)
    assert res["spearman"] > 0.8


def test_data_load_e1_sample(tmp_path):
    from models.logic_eval.data import load_e1_sample
    import gzip

    # Synthetic manifest
    entries = [
        {"id": "f1.c", "source": "human", "excluded": False, "dup_group": "g1", "block": "B1", "assignment": "A/1"},
        {"id": "f2.c", "source": "human", "excluded": False, "dup_group": "g1", "block": "B1", "assignment": "A/1"}, # dup -> drop
        {"id": "f3.c", "source": "human", "excluded": True, "dup_group": "g2", "block": "B1", "assignment": "A/1"}, # excluded -> drop
        {"id": "f4.c", "source": "ai", "excluded": False, "dup_group": "g3", "block": "B1", "assignment": "A/1"}, # ai -> drop
        {"id": "f5.c", "source": "human", "excluded": False, "dup_group": "g4", "block": "B1", "assignment": "A/1"},
        {"id": "f6.c", "source": "human", "excluded": False, "dup_group": "g5", "block": "B2", "assignment": "B/1"},
    ]
    manifest = {"entries": entries, "blocks": {"B1": {}, "B2": {}}}
    p = tmp_path / "split_test.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(manifest, f)

    sample = load_e1_sample(p, max_per_block=10, seed=42)
    ids = [e["id"] for e in sample]
    assert "f1.c" in ids
    assert "f2.c" not in ids  # only 1 per dup_group
    assert "f3.c" not in ids  # excluded
    assert "f4.c" not in ids  # non-human
    assert "f5.c" in ids
    assert "f6.c" in ids
    assert len(sample) == 3


def test_data_load_e2_stats(tmp_path):
    from models.logic_eval.data import load_e2_stats

    # Create synthetic stats dir
    stats_dir = tmp_path / "stats"
    c_dir = stats_dir / "A2016"
    c_dir.mkdir(parents=True)

    # 5 passing students, 3 failing students, 1 empty, 1 0/0
    entries = []
    for i in range(5):
        s_id = f"student{100 + i}"
        (c_dir / f"{s_id}.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "10/10"}}))
        entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": f"f{i}.c", "source": "human", "excluded": False})

    for i in range(3):
        s_id = f"student{200 + i}"
        (c_dir / f"{s_id}.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "3/10"}}))
        entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": f"f{5+i}.c", "source": "human", "excluded": False})

    # Invalid entries
    (c_dir / "student300.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": ""}}))
    entries.append({"course": "A2016", "student": "student300", "assignment": "A2016/Z1/Z1", "id": "f_empty.c", "source": "human", "excluded": False})
    (c_dir / "student301.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "0/0"}}))
    entries.append({"course": "A2016", "student": "student301", "assignment": "A2016/Z1/Z1", "id": "f_zero.c", "source": "human", "excluded": False})

    qualified = load_e2_stats(entries, stats_dir=stats_dir, min_pass=5, min_fail=3)
    assert "A2016/Z1/Z1" in qualified
    q_entries = qualified["A2016/Z1/Z1"]
    assert len(q_entries) == 8
    n_pass = sum(1 for e in q_entries if e["pasa"])
    n_fail = sum(1 for e in q_entries if not e["pasa"])
    assert n_pass == 5
    assert n_fail == 3


def test_data_load_e2_dedup_and_inconsistent(tmp_path):
    from models.logic_eval.data import load_e2_stats

    stats_dir = tmp_path / "stats"
    c_dir = stats_dir / "A2016"
    c_dir.mkdir(parents=True)

    # 6 passing students: 2 share dup_group 'dg-pass' with identical 10/10 result -> keep 1
    # 1 student with multiple files in same assignment -> keep 1
    entries = []
    for i in range(4):
        s_id = f"student10{i}"
        (c_dir / f"{s_id}.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "10/10"}}))
        entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": f"pass_{i}.c", "dup_group": f"dg_{i}", "source": "human", "excluded": False})

    # Two students sharing dup_group 'dg-pass' with same result
    for i in range(2):
        s_id = f"student11{i}"
        (c_dir / f"{s_id}.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "10/10"}}))
        entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": f"pass_dup_{i}.c", "dup_group": "dg-pass", "source": "human", "excluded": False})

    # Student 120 with multiple files in the same assignment
    s_id = "student120"
    (c_dir / f"{s_id}.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "10/10"}}))
    entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": "pass_mult_1.c", "dup_group": "dg_m1", "source": "human", "excluded": False})
    entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": "pass_mult_2.c", "dup_group": "dg_m2", "source": "human", "excluded": False})

    # 4 failing students: 2 share dup_group 'dg-inconsistent' with DIFFERENT results -> discard both!
    # And 3 individual failing students
    for i in range(3):
        s_id = f"student20{i}"
        (c_dir / f"{s_id}.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "3/10"}}))
        entries.append({"course": "A2016", "student": s_id, "assignment": "A2016/Z1/Z1", "id": f"fail_{i}.c", "dup_group": f"dg_fail_{i}", "source": "human", "excluded": False})

    # Inconsistent pair
    (c_dir / "student210.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "5/10"}}))
    entries.append({"course": "A2016", "student": "student210", "assignment": "A2016/Z1/Z1", "id": "inconsist_1.c", "dup_group": "dg-inconsistent", "source": "human", "excluded": False})
    (c_dir / "student211.json").write_text(json.dumps({"A2016/Z1/Z1": {"last_test_results": "2/10"}}))
    entries.append({"course": "A2016", "student": "student211", "assignment": "A2016/Z1/Z1", "id": "inconsist_2.c", "dup_group": "dg-inconsistent", "source": "human", "excluded": False})

    qualified = load_e2_stats(entries, stats_dir=stats_dir, min_pass=5, min_fail=3, seed=42)
    assert "A2016/Z1/Z1" in qualified
    q_entries = qualified["A2016/Z1/Z1"]
    
    # Passing: 4 individual + 1 from dg-pass + 1 from student120 = 6 pass
    # Failing: 3 individual (dg-inconsistent discarded) = 3 fail
    assert len(q_entries) == 9
    assert sum(1 for e in q_entries if e["pasa"]) == 6
    assert sum(1 for e in q_entries if not e["pasa"]) == 3
    # Verify dg-inconsistent was completely excluded
    assert not any(e["dup_group"] == "dg-inconsistent" for e in q_entries)
    # Verify dg-pass only has 1 representative
    assert sum(1 for e in q_entries if e["dup_group"] == "dg-pass") == 1

