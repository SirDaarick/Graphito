"""Tests for the objective external-point rule of the cluster showcase figure."""

import numpy as np

from models.logic_eval.plots import select_external_point


def _synthetic():
    # 2D directions; cosine similarity is determined by the angle.
    # Panel tasks P1, P2 sit around angle 0 and 20 degrees.
    angles = {
        "P1": [0, 2, 4],
        "P2": [18, 20, 22],
        "NEAR": [10, 12, 14],     # close to the panel set
        "FAR": [88, 90, 92],      # far from the panel set
        "MID": [40, 45, 50],
    }
    labels, vecs = [], []
    for task, degs in angles.items():
        for d in degs:
            labels.append(task)
            r = np.deg2rad(d)
            vecs.append([np.cos(r), np.sin(r)])
    emb = np.asarray(vecs)
    sim = emb @ emb.T
    return sim, labels


def test_external_rule_picks_lowest_mean_similarity_task():
    sim, labels = _synthetic()
    res = select_external_point(sim, labels, ["P1", "P2"])
    assert res["task"] == "FAR"
    # The reported score must equal the mean similarity to the panel union.
    lab = np.array(labels)
    panel = np.flatnonzero(np.isin(lab, ["P1", "P2"]))
    far = np.flatnonzero(lab == "FAR")
    assert abs(res["mean_similarity_to_panel"] - sim[np.ix_(far, panel)].mean()) < 1e-12
    # The chosen solution belongs to that task and has the lowest mean similarity.
    assert lab[res["index"]] == "FAR"
    per_point = sim[np.ix_(far, panel)].mean(axis=1)
    assert res["index"] == int(far[int(np.argmin(per_point))])


def test_external_rule_never_picks_a_panel_task():
    sim, labels = _synthetic()
    # Even when a panel task is the globally most dissimilar one.
    res = select_external_point(sim, labels, ["P1", "FAR"])
    assert res["task"] not in ("P1", "FAR")
    assert labels[res["index"]] not in ("P1", "FAR")


def test_external_rule_is_deterministic_with_ties():
    # Two identical candidate tasks: ties are broken by task name, then index.
    emb = np.array([[1, 0], [1, 0], [0, 1], [0, 1], [0, 1], [0, 1]], dtype=float)
    labels = ["P", "P", "T2", "T2", "T1", "T1"]
    sim = emb @ emb.T
    first = select_external_point(sim, labels, ["P"])
    second = select_external_point(sim, labels, ["P"])
    assert first == second
    assert first["task"] == "T1"
    assert first["index"] == 4


def test_cluster_showcase_reuses_fixed_selection(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    from models.logic_eval.plots import plot_cluster_showcase

    rng = np.random.default_rng(0)
    tasks = ["T1", "T2", "T3", "T4", "T5"]
    centers = rng.normal(size=(len(tasks), 16))
    labels, vecs = [], []
    for t, c in zip(tasks, centers):
        for _ in range(40):
            labels.append(t)
            vecs.append(c + 0.3 * rng.normal(size=16) + 3.0)
    emb = np.asarray(vecs)
    fixed = {"panel_a_tasks": ["T1", "T2", "T3"], "panel_b_tasks": ["T4", "T5"], "external_index": 170}
    info = plot_cluster_showcase(
        emb, labels, tmp_path / "f.png", json_path=tmp_path / "f.json", seeds=(42,), dpi=50,
        fixed_selection=fixed,
    )
    assert info["distinct_triplet"]["tasks"] == ["T1", "T2", "T3"]
    assert info["similar_pair"]["tasks"] == ["T4", "T5"]
    assert info["external_point"]["solution_index"] == 170
    assert info["external_point"]["task"] == "T5"
    assert info["selection"] == "reused"
    assert (tmp_path / "f.png").is_file() and (tmp_path / "f.json").is_file()
