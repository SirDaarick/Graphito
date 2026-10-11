"""Pair scoring within assignment, views and MAP@R for the GraphCodeBERT v2 evaluation (GV1.2, GV4).

Synthetic data only: hand-built `PairSet`/`Sample` cases and the `eval_factory` corpus manifest.
"""

from dataclasses import replace

import numpy as np
import pytest

from eval_factory import make_tree
from models.evaluation import metrics as M
from models.evaluation.manifest import PairSet, Sample, load_manifest
from models.evaluation.splits import SplitConfig, build_split, write_manifest
from models.graphcodebert.v2 import pairs as P

BASE = Sample(
    id="", course="A2016", block="A/Z1", assignment="A/Z1/Z1", student=None, lang="c", source="human",
    model=None, profile=None, sha256="0" * 64, norm_hash="h0", n_tokens=100, dup_group=None, dup_rep=None,
    cluster_id=None, gt_status="negative", split="val", excluded=False, flags=(),
)


def sample(id_, assignment, student, cluster=None, norm_hash=None):
    return replace(
        BASE, id=id_, assignment=assignment, student=student, cluster_id=cluster,
        gt_status="positive" if cluster else "negative", norm_hash=norm_hash or f"h-{id_}",
        sha256=f"{abs(hash(id_)):064d}"[-64:],
    )


def pairset(samples):
    """Same construction as `SplitManifest.plagiarism_pairs` for the given labelled samples."""
    pool = sorted(samples, key=lambda s: (s.assignment, s.id))
    a, b, label, assignment = [], [], [], []
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            si, sj = pool[i], pool[j]
            if si.assignment != sj.assignment or si.student == sj.student:
                continue
            a.append(i)
            b.append(j)
            label.append(int(si.cluster_id is not None and si.cluster_id == sj.cluster_id))
            assignment.append(si.assignment)
    n = len(a)
    return PairSet(
        np.array(a, dtype=np.int64), np.array(b, dtype=np.int64), np.array(label, dtype=np.int8),
        np.array(assignment, dtype=object), [s.id for s in pool], np.zeros(n, dtype=bool),
    ), {s.id: s for s in pool}


def views_case():
    # X: s1,s2 same cluster and identical; s3 identical to both, no cluster; s4 different.
    # Y: two unrelated files.
    samples = [
        sample("x1", "X", "s1", "c1", "same"),
        sample("x2", "X", "s2", "c1", "same"),
        sample("x3", "X", "s3", None, "same"),
        sample("x4", "X", "s4", None, "other"),
        sample("y1", "Y", "s1", None, "y1"),
        sample("y2", "Y", "s2", None, "y2"),
    ]
    return P.EvalPairs.build(*pairset(samples))


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    tree = make_tree(tmp_path_factory.mktemp("corpus"))
    config = SplitConfig(
        seed=7, repo_root=tree.repo_root, raw_root=tree.raw_root, ai_root=tree.ai_root,
        gt_static=tree.gt_static, gt_ambiguous=(tree.gt_dynamic,),
    )
    return load_manifest(write_manifest(build_split(config), tree.repo_root / "split.json"))


def test_blocks_map_pair_indices_to_ids_of_their_assignment(manifest):
    ep = P.EvalPairs.from_manifest(manifest, "val")
    pairs = ep.pairs
    assert pairs.a.size > 0 and ep.split == "val"
    by_id = {s.id: s for s in manifest.samples("val")}
    for assignment, start, stop in ep.blocks:
        assert all(by_id[i].assignment == assignment for i in pairs.ids[start:stop])
    for k in range(pairs.a.size):
        ia, ib = pairs.ids[pairs.a[k]], pairs.ids[pairs.b[k]]
        assert by_id[ia].assignment == by_id[ib].assignment == pairs.assignment[k]
        assert by_id[ia].split == by_id[ib].split == "val"
        assert by_id[ia].student != by_id[ib].student
        assert ep.samples[pairs.a[k]].id == ia and ep.samples[pairs.b[k]].id == ib


def test_embedding_scores_equal_brute_force_cosine(manifest):
    ep = P.EvalPairs.from_manifest(manifest, "test")
    rng = np.random.default_rng(0)
    emb = rng.normal(size=(len(ep.pairs.ids), 16))
    scored = P.score_pairs(P.embedding_similarity(emb), ep)
    unit = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    brute = np.einsum("ij,ij->i", unit[ep.pairs.a], unit[ep.pairs.b])
    np.testing.assert_allclose(scored.scores, brute, atol=1e-12)


def test_zero_embedding_rows_score_zero():
    ep = views_case()
    emb = np.ones((len(ep.pairs.ids), 4))
    emb[0] = 0.0  # a failed embedding
    scored = P.score_pairs(P.embedding_similarity(emb), ep)
    touching = (ep.pairs.a == 0) | (ep.pairs.b == 0)
    assert np.all(scored.scores[touching] == 0.0) and np.allclose(scored.scores[~touching], 1.0)


def test_views_drop_only_identical_negatives():
    ep = views_case()
    ids = ep.pairs.ids
    keep = ep.view_mask("no_identical")
    dropped = {(ids[a], ids[b]) for a, b, k in zip(ep.pairs.a, ep.pairs.b, keep) if not k}
    assert dropped == {("x1", "x3"), ("x2", "x3")}
    assert ep.view_mask("all").all() and ep.dropped("all") == 0 and ep.dropped("no_identical") == 2
    k12 = [k for k, (a, b) in enumerate(zip(ep.pairs.a, ep.pairs.b)) if (ids[a], ids[b]) == ("x1", "x2")]
    assert ep.pairs.label[k12[0]] == 1 and keep[k12[0]]  # identical positive kept
    with pytest.raises(ValueError):
        ep.view_mask("bogus")


def test_map_at_r_per_assignment_and_identical_negatives_removed():
    ep = views_case()
    # x3 (identical negative) is the nearest neighbour of x1 and x2.
    emb = np.array(
        [[1.0, 0.0, 0.0], [0.6, 0.8, 0.0], [0.9, 0.3, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    )
    scored = P.score_pairs(P.embedding_similarity(emb), ep)
    unit = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    labels = ["c1", "c1", None, None]
    expected_all = M.map_at_r(unit[:4] @ unit[:4].T, labels)
    assert scored.map_at_r["all"]["per_assignment"]["X"] == expected_all
    assert scored.map_at_r["all"]["value"] == pytest.approx(expected_all["value"])
    assert expected_all["value"] == pytest.approx(0.0)  # x3 ranks first for both queries
    assert scored.map_at_r["no_identical"]["value"] == pytest.approx(1.0)
    assert scored.map_at_r["all"]["per_assignment"]["Y"]["n_queries"] == 0
    assert scored.map_at_r["all"]["n_queries"] == 2


def test_same_student_candidates_are_counted():
    samples = [sample("a1", "A", "s1", "c"), sample("a2", "A", "s2", "c"), sample("a3", "A", "s1")]
    ep = P.EvalPairs.build(*pairset(samples))
    assert ep.same_student_pairs == 1
    assert views_case().same_student_pairs == 0


def test_map_at_r_ci_resamples_assignments_reproducibly():
    per = {
        "A": {"value": 1.0, "n_queries": 2, "n_excluded": 0, "ap_sum": 2.0},
        "B": {"value": 0.0, "n_queries": 2, "n_excluded": 1, "ap_sum": 0.0},
        "C": {"value": None, "n_queries": 0, "n_excluded": 3, "ap_sum": 0.0},
    }
    one = P.map_at_r_ci(per, n_boot=200, seed=3)
    assert one == P.map_at_r_ci(per, n_boot=200, seed=3)
    assert one["value"] == pytest.approx(0.5) and one["unit"] == "assignment" and one["n_units"] == 3
    lo, hi = one["ci95"]
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0
    none = P.map_at_r_ci({"C": per["C"]}, n_boot=50, seed=3)
    assert none["value"] is None and none["ci95"] is None and none["reason"] == "no_queries"


def test_limit_assignments_keeps_the_first_assignments(manifest):
    full = P.EvalPairs.from_manifest(manifest, "val")
    small = P.EvalPairs.from_manifest(manifest, "val", limit_assignments=1)
    first = full.blocks[0][0]
    assert [b[0] for b in small.blocks] == [first]
    assert set(small.pairs.assignment) == {first}
    keep = full.pairs.assignment == first
    assert small.pairs.a.size == int(keep.sum())
    assert list(small.pairs.label) == list(full.pairs.label[keep])


def test_exclusions_are_counted(manifest):
    ep = P.EvalPairs.from_manifest(manifest, "val")
    ex = ep.exclusions
    assert set(ex) >= {"ambiguous_pairs", "unlabeled_pairs", "ambiguous_files", "unlabeled_files"}
    amb = manifest.plagiarism_pairs("val", include_ambiguous=True)
    assert ex["ambiguous_pairs"] == int(amb.ambiguous.sum())
    labelled = {s.id for s in manifest.samples("val", source="human") if s.gt_status in ("positive", "negative")}
    assert set(ep.pairs.ids) == labelled
