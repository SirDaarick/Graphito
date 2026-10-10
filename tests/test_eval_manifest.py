"""Split manifest loader: schema validation, hashing, split filters and GT views."""

import dataclasses
import hashlib
import json

import numpy as np
import pytest

import models.evaluation as evaluation
from eval_factory import make_tree
from models.evaluation.manifest import (
    DEFAULT_MANIFEST,
    ManifestError,
    ManifestHashError,
    PairSet,
    Sample,
    SplitManifest,
    load_manifest,
    load_split,
)
from models.evaluation.splits import SplitConfig, build_split, write_manifest


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    tree = make_tree(tmp_path_factory.mktemp("corpus"))
    config = SplitConfig(
        seed=7,
        repo_root=tree.repo_root,
        raw_root=tree.raw_root,
        ai_root=tree.ai_root,
        gt_static=tree.gt_static,
        gt_ambiguous=(tree.gt_dynamic,),
    )
    path = write_manifest(build_split(config), tree.repo_root / "data" / "splits" / "split_v1.json")
    return tree, path


@pytest.fixture(scope="module")
def manifest(corpus):
    return load_manifest(corpus[1])


def _rewrite(path, tmp_path, mutate):
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    out = tmp_path / "edited.json"
    out.write_text(json.dumps(data), encoding="utf-8")
    return out


def test_load_split_returns_only_that_split_without_broken_or_excluded(corpus):
    val = load_split("val", path=corpus[1])
    assert val and all(isinstance(s, Sample) for s in val)
    assert all(s.split == "val" and not s.broken and not s.excluded for s in val)


def test_include_broken_returns_broken_entries(corpus, manifest):
    broken_id = corpus[0].ids["empty"]
    split = manifest.split_of(broken_id)
    assert broken_id not in {s.id for s in load_split(split, path=corpus[1])}
    with_broken = load_split(split, path=corpus[1], include_broken=True)
    assert broken_id in {s.id for s in with_broken}
    total = sum(len(load_split(s, path=corpus[1], include_broken=True)) for s in ("train", "val", "test"))
    pinned = manifest.stats["excluded"]["cross_split_dup"]
    assert total == len(manifest.entries) - pinned  # cross_split_dup stays out unless asked


def test_filters_by_lang_source_and_course(corpus, manifest):
    for split in ("train", "val", "test"):
        cpp_ai = load_split(split, path=corpus[1], lang="cpp", source="ai")
        assert cpp_ai and all(s.lang == "cpp" and s.source == "ai" for s in cpp_ai)
    a2016 = manifest.samples(course="A2016")
    assert a2016 and all(s.course == "A2016" for s in a2016)
    excluded = manifest.samples(include_excluded=True, include_broken=True)
    assert len(excluded) == len(manifest.entries)


def test_unknown_split_name_is_rejected(corpus):
    with pytest.raises(ValueError, match="split"):
        load_split("dev", path=corpus[1])


def test_sha256_is_computed_from_the_file_bytes(corpus, manifest):
    assert manifest.sha256 == hashlib.sha256(corpus[1].read_bytes()).hexdigest()
    assert load_manifest(corpus[1], expected_sha256=manifest.sha256).sha256 == manifest.sha256
    assert "sha256" not in json.loads(corpus[1].read_text(encoding="utf-8"))  # never embedded


def test_expected_sha256_mismatch_raises(corpus):
    with pytest.raises(ManifestHashError, match="sha256"):
        load_manifest(corpus[1], expected_sha256="0" * 64)
    with pytest.raises(ManifestHashError):
        load_split("test", path=corpus[1], expected_sha256="0" * 64)


def test_manifest_edited_after_generation_fails_the_hash_check(corpus, tmp_path, manifest):
    edited = tmp_path / "split.json"
    edited.write_bytes(corpus[1].read_bytes().replace(b'"split":"train"', b'"split":"val"', 1))
    with pytest.raises(ManifestHashError):
        load_manifest(edited, expected_sha256=manifest.sha256)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d.update(schema="graphito.split/v0"), "schema"),
        (lambda d: d.pop("stats"), "stats"),
        (lambda d: d["entries"][0].pop("norm_hash"), "norm_hash"),
        (lambda d: d["entries"][0].update(split="dev"), "split"),
        (lambda d: d["entries"][0].update(source="robot"), "source"),
        (lambda d: d["entries"][0].update(flags="broken"), "flags"),
        (lambda d: d["entries"].__setitem__(0, "oops"), "object"),
        (lambda d: d["entries"].__setitem__(0, 42), "object"),
        (lambda d: d["entries"].__setitem__(0, ["id", "split"]), "object"),
        (lambda d: d["entries"][0].update(split=["train"]), "split"),
        (lambda d: d["entries"][0].update(lang={"c": 1}), "lang"),
        (lambda d: d["entries"][0].update(gt_status=[]), "gt_status"),
    ],
)
def test_schema_validation_rejects_bad_files(corpus, tmp_path, mutate, message):
    with pytest.raises(ManifestError, match=message):
        load_manifest(_rewrite(corpus[1], tmp_path, mutate))


def test_non_json_file_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="JSON"):
        load_manifest(bad)


def test_channel_a_negatives_never_include_unlabeled_entries(manifest):
    negatives = manifest.channel_a_negatives()
    assert negatives
    assert all(s.gt_status == "negative" and s.source == "human" for s in negatives)
    assert not any(s.course == "B2017" for s in negatives)
    assert not any(s.assignment == "A2017/Z6/Z1" for s in negatives)  # unheaded assignment
    for split in ("train", "val", "test"):
        assert all(s.split == split for s in manifest.channel_a_negatives(split))


def test_plagiarism_pairs_label_same_cluster_pairs(manifest):
    for split in ("train", "val", "test"):
        pairs = manifest.plagiarism_pairs(split)
        assert isinstance(pairs, PairSet)
        assert len(pairs.a) == len(pairs.b) == len(pairs.label) == len(pairs.assignment)
        assert np.all(pairs.a < pairs.b)
        by_id = {s.id: s for s in manifest.entries}
        for a, b, y, asg in zip(pairs.a, pairs.b, pairs.label, pairs.assignment):
            sa, sb = by_id[pairs.ids[a]], by_id[pairs.ids[b]]
            assert sa.assignment == sb.assignment == asg and sa.split == split
            assert sa.student != sb.student
            assert {sa.gt_status, sb.gt_status} <= {"positive", "negative"}
            assert y == int(sa.cluster_id is not None and sa.cluster_id == sb.cluster_id)
        assert not any(by_id[i].course == "B2017" for i in pairs.ids)
        assert pairs.ambiguous.dtype == bool and len(pairs.ambiguous) == len(pairs.a)
        assert not pairs.ambiguous.any()
    every = [manifest.plagiarism_pairs(s) for s in ("train", "val", "test")]
    assert sum(int(p.label.sum()) for p in every) >= 1


def _id_pairs(pairs, mask=None):
    keep = np.ones(len(pairs.a), dtype=bool) if mask is None else mask
    return {(pairs.ids[a], pairs.ids[b]) for a, b in zip(pairs.a[keep], pairs.b[keep])}


def test_plagiarism_pairs_include_ambiguous_on_request(manifest):
    split = manifest.split_of("data/raw/src/A2016/Z3/Z1/student1003.c")  # dynamic-only student
    base = manifest.plagiarism_pairs(split)
    wider = manifest.plagiarism_pairs(split, include_ambiguous=True)
    assert len(wider.a) > len(base.a)
    by_id = {s.id: s for s in manifest.entries}
    for a, b, y, amb in zip(wider.a, wider.b, wider.label, wider.ambiguous):
        statuses = {by_id[wider.ids[a]].gt_status, by_id[wider.ids[b]].gt_status}
        assert bool(amb) == ("ambiguous" in statuses)
        assert y == -1 if amb else y in (0, 1)  # ambiguous pairs are never true negatives
    assert wider.ambiguous.any()
    assert _id_pairs(wider, ~wider.ambiguous) == _id_pairs(base)
    assert np.array_equal(np.sort(wider.label[~wider.ambiguous]), np.sort(base.label))


def test_representatives_only_keeps_one_included_member_per_group(corpus, manifest):
    """The representative is chosen within the result set, so pinned groups whose global
    `dup_rep` is excluded (or in another split) still keep one member."""
    cross = {v for k, v in corpus[0].ids.items() if k.startswith("cross_exact_")}
    covered, moved = set(), 0
    for split in ("train", "val", "test"):
        for include_excluded in (False, True):
            full = manifest.samples(split, include_excluded=include_excluded)
            reps = manifest.samples(split, include_excluded=include_excluded, representatives_only=True)
            groups = {}
            for s in full:
                if s.dup_group is not None:
                    groups.setdefault(s.dup_group, []).append(s.id)
            kept = [s for s in reps if s.dup_group is not None]
            assert sorted(s.dup_group for s in kept) == sorted(groups)  # exactly one per group
            assert all(s.id == min(groups[s.dup_group]) for s in kept)
            assert [s for s in reps if s.dup_group is None] == [s for s in full if s.dup_group is None]
            moved += sum(s.id != s.dup_rep for s in kept)
            if not include_excluded and cross & {s.id for s in full}:
                covered.add(split)
    assert covered  # the pinned cross-block exact group keeps a representative
    assert moved  # at least one representative differs from the global `dup_rep`


def test_representatives_only_respects_lang_and_source_filters(manifest):
    for split in ("train", "val", "test"):
        for lang, source in (("c", "human"), ("cpp", "ai")):
            full = manifest.samples(split, lang=lang, source=source)
            reps = manifest.samples(split, lang=lang, source=source, representatives_only=True)
            groups = {s.dup_group for s in full if s.dup_group is not None}
            assert sorted(s.dup_group for s in reps if s.dup_group is not None) == sorted(groups)


def test_clusters_group_member_ids_per_split(manifest):
    every = manifest.clusters()
    assert every["A2016/Z1/Z1#01"] == sorted(manifest.groups["clusters"]["A2016/Z1/Z1#01"]["members"])
    for split in ("train", "val", "test"):
        for cid, members in manifest.clusters(split).items():
            assert {manifest.split_of(m) for m in members} == {split}


def test_check_invariants_passes_and_detects_tampering(corpus, tmp_path, manifest):
    manifest.check_invariants()

    def tamper(data):
        entry = next(e for e in data["entries"] if e["block"] == "B/Z1")
        entry["split"] = next(s for s in ("train", "val", "test") if s != entry["split"])

    tampered = load_manifest(_rewrite(corpus[1], tmp_path, tamper))
    with pytest.raises(ManifestError, match="block B/Z1"):
        tampered.check_invariants()


def test_check_invariants_names_the_first_missing_stratum(corpus, tmp_path):
    def strip(data):  # test and val lose C++ and AI; train keeps both
        for e in data["entries"]:
            if e["split"] in ("test", "val"):
                e.update(lang="c", source="human")

    stripped = load_manifest(_rewrite(corpus[1], tmp_path, strip))
    with pytest.raises(ManifestError, match=r"^split 'test' lacks stratum lang=cpp$"):
        stripped.check_invariants()


def test_samples_are_frozen_and_split_of_rejects_unknown_ids(manifest):
    sample = manifest.entries[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sample.split = "test"
    assert isinstance(sample.flags, tuple)
    with pytest.raises(KeyError):
        manifest.split_of("data/raw/src/nope.c")


def test_package_exports_and_default_path():
    assert evaluation.load_split is load_split
    assert evaluation.SplitManifest is SplitManifest
    assert DEFAULT_MANIFEST.as_posix().endswith("data/splits/split_v1.json")
