"""CharCNN v2 data pipeline: manifest-backed encoded sets and the seeded 1:1 epoch sampler.

The manifest comes from the synthetic `eval_factory` corpus written into a temporary directory;
the sampler tests use small synthetic encoded sets. CPU only, no model.
"""

from collections import Counter

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from eval_factory import make_tree
from models.char_cnn.v2.data import (
    VIEWS,
    EncodedSet,
    collate,
    epoch_batches,
    label_of,
    load_encoded,
    load_views,
    view_samples,
)
from models.char_cnn.v2.config import CharCNNV2Config
from models.char_cnn.v2.preprocess import encode, preprocess_v2
from models.evaluation.manifest import Sample, load_manifest
from models.evaluation.splits import SplitConfig, build_split, write_manifest

WINDOW = CharCNNV2Config().window


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
    return tree, load_manifest(path)


@pytest.fixture(scope="module")
def loaded(corpus):
    tree, manifest = corpus
    calls = []
    views = load_views(manifest, root=tree.repo_root, on_text=lambda s, raw, norm: calls.append((s, raw, norm)))
    return views, calls


def _raw(tree, sample_id: str) -> str:
    return (tree.repo_root / sample_id).read_bytes().decode("utf-8", errors="replace")


class TestLoadEncoded:
    def test_views_are_manifest_representatives(self, corpus, loaded):
        _, manifest = corpus
        views, _ = loaded
        assert set(views) == set(VIEWS) == {"train", "val", "test", "test_all"}
        for name, (split, reps) in VIEWS.items():
            expected = [s.id for s in manifest.samples(split, representatives_only=reps)]
            assert views[name].ids == expected, name
            assert [s.id for s in view_samples(manifest, name)] == expected
        all_files = sum(len(manifest.samples(split)) for split in ("train", "val", "test"))
        reps = sum(len(views[name]) for name in ("train", "val", "test"))
        assert reps < all_files  # the fixture has dup groups, so representatives matter

    def test_labels_follow_source(self, loaded):
        views, _ = loaded
        for view in views.values():
            assert view.y.dtype == np.int64
            assert view.y.tolist() == [int(s.source == "ai") for s in view.samples]
            assert view.y.tolist() == [label_of(s) for s in view.samples]
        assert {0, 1} <= set(views["train"].y.tolist())

    def test_broken_entries_are_excluded(self, corpus, loaded):
        tree, manifest = corpus
        views, _ = loaded
        broken = {s.id for s in manifest.samples(include_broken=True) if s.broken}
        assert tree.ids["empty"] in broken and tree.ids["too_short"] in broken
        for view in views.values():
            assert not broken & set(view.ids)

    def test_arrays_are_encoded_normalized_text(self, corpus, loaded):
        tree, _ = corpus
        views, _ = loaded
        for sample, arr in zip(views["val"].samples, views["val"].arrays):
            assert arr.dtype == np.uint8
            np.testing.assert_array_equal(arr, encode(preprocess_v2(_raw(tree, sample.id))))

    def test_on_text_called_once_per_file(self, corpus, loaded):
        tree, _ = corpus
        views, calls = loaded
        counts = Counter(s.id for s, _, _ in calls)
        assert set(counts.values()) == {1}
        assert set(counts) == set().union(*(set(v.ids) for v in views.values()))
        for sample, raw, normalized in calls:
            assert isinstance(sample, Sample)
            assert raw == _raw(tree, sample.id)
            assert normalized == preprocess_v2(raw)

    def test_non_representatives_are_never_read_by_representative_views(self, corpus):
        # Without `test_all`, only representatives are read (as for train, which has no
        # all-files view); the fixture's non-representatives sit in val/test.
        tree, manifest = corpus
        read = []
        load_views(
            manifest,
            views=("train", "val", "test"),
            root=tree.repo_root,
            on_text=lambda s, raw, norm: read.append(s.id),
        )
        non_reps = set()
        for split in ("train", "val", "test"):
            reps = {s.id for s in manifest.samples(split, representatives_only=True)}
            non_reps |= {s.id for s in manifest.samples(split)} - reps
        assert non_reps
        assert not non_reps & set(read)

    def test_splits_do_not_overlap(self, loaded):
        views, _ = loaded
        train, val, test = (set(views[n].ids) for n in ("train", "val", "test"))
        assert not (train & val or train & test or val & test)
        assert test <= set(views["test_all"].ids)

    def test_shared_files_share_arrays(self, loaded):
        views, _ = loaded
        by_id = dict(zip(views["test_all"].ids, views["test_all"].arrays))
        for sample_id, arr in zip(views["test"].ids, views["test"].arrays):
            assert arr is by_id[sample_id]

    def test_missing_files_raise_with_count(self, corpus, tmp_path):
        tree, manifest = corpus
        samples = view_samples(manifest, "val")
        for sample in samples[2:]:
            target = tmp_path / sample.id
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((tree.repo_root / sample.id).read_bytes())
        with pytest.raises(FileNotFoundError, match=rf"2 of {len(samples)} "):
            load_encoded(manifest, samples, root=tmp_path)

    def test_invalid_utf8_is_replaced(self, corpus, tmp_path):
        _, manifest = corpus
        sample = view_samples(manifest, "val")[0]
        target = tmp_path / sample.id
        target.parent.mkdir(parents=True)
        target.write_bytes(b"int main() {\xff\xfe return 0; }\n")
        out = load_encoded(manifest, [sample], root=tmp_path)
        np.testing.assert_array_equal(out.arrays[0], encode("int main() { return 0; }"))

    def test_foreign_sample_is_rejected(self, corpus):
        tree, manifest = corpus
        sample = view_samples(manifest, "val")[0]
        foreign = Sample(**{**sample.__dict__, "id": "data/raw/src/nowhere.c"})
        with pytest.raises(ValueError, match="not in the manifest"):
            load_encoded(manifest, [foreign], root=tree.repo_root)

    def test_sample_with_another_split_is_rejected_with_both_splits(self, corpus):
        tree, manifest = corpus
        sample = view_samples(manifest, "val")[0]
        moved = Sample(**{**sample.__dict__, "split": "train"})
        with pytest.raises(ValueError, match=r"split 'train' but the manifest has 'val'") as info:
            load_encoded(manifest, [moved], root=tree.repo_root)
        assert "not in the manifest" not in str(info.value)

    def test_unknown_view_is_rejected(self, corpus):
        with pytest.raises(ValueError, match="view"):
            view_samples(corpus[1], "train_all")


def _sample(sample_id: str, source: str) -> Sample:
    return Sample(
        id=sample_id, course="A2016", block="A/Z1", assignment="A/Z1/Z1", student=None, lang="c",
        source=source, model=None, profile=None, sha256="0", norm_hash="0", n_tokens=10,
        dup_group=None, dup_rep=None, cluster_id=None, gt_status=None, split="train",
        excluded=False, flags=(),
    )


def _set(n_ai: int, n_human: int, lengths=None) -> EncodedSet:
    samples = [_sample(f"ai{i:02d}.c", "ai") for i in range(n_ai)]
    samples += [_sample(f"h{i:02d}.c", "human") for i in range(n_human)]
    lengths = lengths or [20 + 7 * i for i in range(len(samples))]
    arrays = [np.full(n, 2 + i % 90, dtype=np.uint8) for i, n in enumerate(lengths)]
    return EncodedSet.build(samples, arrays)


def _ids(train: EncodedSet, plan) -> list[str]:
    return [train.ids[i] for batch in plan.batches for i in batch.indices]


class TestEpochs:
    def test_balanced_epoch_uses_all_ai_and_equal_humans(self):
        train = _set(3, 10)
        plan = epoch_batches(train, epoch=0, seed=1, batch_size=2, window=WINDOW)
        ids = _ids(train, plan)
        assert sorted(i for i in ids if i.startswith("ai")) == ["ai00.c", "ai01.c", "ai02.c"]
        assert sum(i.startswith("h") for i in ids) == 3
        assert len(ids) == len(set(ids)) == 6
        assert (plan.n_ai, plan.n_human, plan.n_human_available, plan.human_shortfall) == (3, 3, 10, 0)

    def test_epoch_is_reproducible_and_varies(self):
        train = _set(3, 10)
        humans = {}
        for epoch in range(4):
            a = epoch_batches(train, epoch=epoch, seed=1, batch_size=2, window=WINDOW)
            b = epoch_batches(train, epoch=epoch, seed=1, batch_size=2, window=WINDOW)
            assert _ids(train, a) == _ids(train, b)
            assert [x.indices for x in a.batches] == [x.indices for x in b.batches]
            humans[epoch] = frozenset(i for i in _ids(train, a) if i.startswith("h"))
        assert humans[0] != humans[1]
        assert len(set(humans.values())) > 1
        other_seed = epoch_batches(train, epoch=0, seed=2, batch_size=2, window=WINDOW)
        same_seed = epoch_batches(train, epoch=0, seed=1, batch_size=2, window=WINDOW)
        assert _ids(train, other_seed) != _ids(train, same_seed)

    def test_human_draw_uses_keyed_rng(self):
        from models.evaluation.seed import stable_rng

        train = _set(3, 10)
        plan = epoch_batches(train, epoch=5, seed=9, batch_size=4, window=WINDOW)
        human_ids = sorted(i for i in train.ids if i.startswith("h"))
        expected = set(stable_rng(9, "epoch5").sample(human_ids, 3))
        assert {i for i in _ids(train, plan) if i.startswith("h")} == expected

    def test_fewer_humans_than_ai_uses_all_and_records_shortfall(self):
        train = _set(5, 2)
        plan = epoch_batches(train, epoch=0, seed=1, batch_size=3, window=WINDOW)
        ids = _ids(train, plan)
        assert sorted(ids) == sorted(train.ids)
        assert (plan.n_ai, plan.n_human, plan.human_shortfall) == (5, 2, 3)
        assert plan.summary() == {
            "epoch": 0, "n_ai": 5, "n_human": 2, "n_human_available": 2, "human_shortfall": 3,
            "n_batches": len(plan.batches),
        }

    def test_crops_are_bounded_and_keyed(self):
        train = _set(1, 1, lengths=[9000, 100])
        a = epoch_batches(train, epoch=0, seed=3, batch_size=2, window=WINDOW)
        b = epoch_batches(train, epoch=0, seed=3, batch_size=2, window=WINDOW)
        crops_a = {train.ids[i]: arr for batch in a.batches for i, arr in zip(batch.indices, batch.arrays)}
        crops_b = {train.ids[i]: arr for batch in b.batches for i, arr in zip(batch.indices, batch.arrays)}
        assert len(crops_a["ai00.c"]) == WINDOW
        assert len(crops_a["h00.c"]) == 100
        np.testing.assert_array_equal(crops_a["ai00.c"], crops_b["ai00.c"])
        long = np.arange(9000) % 90 + 2
        train = EncodedSet.build(train.samples, [long.astype(np.uint8), train.arrays[1]])
        starts = set()
        for epoch in range(6):
            plan = epoch_batches(train, epoch=epoch, seed=3, batch_size=2, window=WINDOW)
            crop = next(arr for batch in plan.batches for i, arr in zip(batch.indices, batch.arrays) if i == 0)
            assert len(crop) == WINDOW
            starts.add(int(crop[0]))
        assert len(starts) > 1

    def test_window_argument_bounds_crops(self):
        train = _set(2, 2, lengths=[300, 50, 400, 10])
        plan = epoch_batches(train, epoch=0, seed=1, batch_size=4, window=64)
        assert max(len(arr) for batch in plan.batches for arr in batch.arrays) == 64

    def test_window_is_required(self):
        # The crop length must come from the run's CharCNNV2Config, never a silent default.
        with pytest.raises(TypeError, match="window"):
            epoch_batches(_set(2, 2), epoch=0, seed=1, batch_size=2)

    def test_batches_are_length_bucketed(self):
        lengths = [5, 90, 40, 300, 12, 77, 150, 33]
        train = _set(4, 4, lengths=lengths)
        plan = epoch_batches(train, epoch=0, seed=4, batch_size=2, window=WINDOW)
        assert all(1 <= len(batch.indices) <= 2 for batch in plan.batches)
        spans = sorted((min(len(a) for a in b.arrays), max(len(a) for a in b.arrays)) for b in plan.batches)
        assert all(prev[1] <= nxt[0] for prev, nxt in zip(spans, spans[1:]))  # disjoint length ranges
        assert [b.labels for b in plan.batches] == [
            tuple(int(train.y[i]) for i in b.indices) for b in plan.batches
        ]

    def test_invalid_arguments(self):
        with pytest.raises(ValueError, match="batch_size"):
            epoch_batches(_set(2, 2), epoch=0, seed=1, batch_size=0, window=WINDOW)
        with pytest.raises(ValueError, match="AI"):
            epoch_batches(_set(0, 3), epoch=0, seed=1, batch_size=2, window=WINDOW)


class TestCollate:
    def test_right_pads_with_zero(self):
        arrays = [np.array([5, 6, 7], dtype=np.uint8), np.array([97], dtype=np.uint8)]
        x, y = collate(arrays, [1, 0])
        assert x.dtype == torch.long and y.dtype == torch.long
        assert x.tolist() == [[5, 6, 7], [97, 0, 0]]
        assert y.tolist() == [1, 0]

    def test_batch_of_one(self):
        x, y = collate([np.array([3], dtype=np.uint8)], [0])
        assert x.shape == (1, 1) and y.tolist() == [0]

    def test_plan_batches_collate(self):
        train = _set(3, 3)
        plan = epoch_batches(train, epoch=0, seed=1, batch_size=4, window=WINDOW)
        for batch in plan.batches:
            x, y = collate(batch.arrays, batch.labels)
            assert x.shape == (len(batch.indices), max(len(a) for a in batch.arrays))
            assert y.tolist() == list(batch.labels)
