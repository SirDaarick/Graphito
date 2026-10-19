"""Tests for CharCNN v2 AI training subsampling (models.char_cnn.v2.subsample).

Invariants tested:
1. Fraction 1.0 returns identical entries.
2. No dup_group is split across any fraction or seed.
3. Nested subsets for identical seed: subset(f1) <= subset(f2) for f1 <= f2.
4. Stratified by task: every task with >=1 group keeps >=1 group (for f > 0).
5. Only train AI entries are subsampled; humans, val and test remain 100% intact.
6. Determinism: identical seed and fraction produce identical outputs.
7. Support for both Sequence[Sample] / Sequence[dict] and EncodedSet.
8. Validation of fraction bounds.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pytest

from models.char_cnn.v2.data import EncodedSet
from models.char_cnn.v2.subsample import subsample_ai_train


@dataclass(frozen=True)
class DummySample:
    id: str
    assignment: str
    dup_group: Optional[str] = None
    source: str = "ai"
    split: str = "train"


def _make_sample(
    id: str,
    assignment: str,
    dup_group: Optional[str] = None,
    source: str = "ai",
    split: str = "train",
) -> DummySample:
    return DummySample(
        id=id,
        assignment=assignment,
        dup_group=dup_group or f"group_{id}",
        source=source,
        split=split,
    )


class TestSubsampleAiTrain:
    def test_invalid_fraction_raises(self):
        entries = [_make_sample("s1", "task1")]
        with pytest.raises(ValueError, match="fraction"):
            subsample_ai_train(entries, fraction=-0.1, seed=42)
        with pytest.raises(ValueError, match="fraction"):
            subsample_ai_train(entries, fraction=1.5, seed=42)
        with pytest.raises(ValueError, match="fraction"):
            subsample_ai_train(entries, fraction=float("nan"), seed=42)

    def test_fraction_one_returns_identical_entries(self):
        entries = [
            _make_sample(f"ai_{i}", f"task_{i % 3}", dup_group=f"g_{i % 5}")
            for i in range(20)
        ]
        result = subsample_ai_train(entries, fraction=1.0, seed=42)
        assert len(result) == len(entries)
        assert [e.id for e in result] == [e.id for e in entries]

    def test_no_dup_group_is_split(self):
        # 4 tasks, 10 dup_groups each, each dup_group has 3 duplicate files
        entries = []
        for t in range(4):
            for g in range(10):
                grp = f"task{t}_grp{g}"
                for rep in range(3):
                    entries.append(
                        _make_sample(
                            id=f"{grp}_file{rep}",
                            assignment=f"task_{t}",
                            dup_group=grp,
                        )
                    )

        for frac in (0.1, 0.25, 0.5, 0.75):
            for seed in (42, 123):
                sub = subsample_ai_train(entries, fraction=frac, seed=seed)
                # Count files per dup_group in output
                from collections import Counter

                counts = Counter(e.dup_group for e in sub)
                for grp, count in counts.items():
                    # Must be exactly 3: either the entire dup_group is included or none of it
                    assert count == 3, f"dup_group {grp} split with count {count}"

    def test_nested_by_seed(self):
        # With the same seed, subset(0.1) c subset(0.2) c subset(0.5) c subset(1.0)
        entries = [
            _make_sample(f"ai_{i}", f"task_{i % 5}", dup_group=f"g_{i}")
            for i in range(100)
        ]
        seed = 2024
        sub_10 = subsample_ai_train(entries, fraction=0.10, seed=seed)
        sub_20 = subsample_ai_train(entries, fraction=0.20, seed=seed)
        sub_50 = subsample_ai_train(entries, fraction=0.50, seed=seed)
        sub_80 = subsample_ai_train(entries, fraction=0.80, seed=seed)
        sub_100 = subsample_ai_train(entries, fraction=1.00, seed=seed)

        ids_10 = {e.id for e in sub_10}
        ids_20 = {e.id for e in sub_20}
        ids_50 = {e.id for e in sub_50}
        ids_80 = {e.id for e in sub_80}
        ids_100 = {e.id for e in sub_100}

        assert ids_10.issubset(ids_20)
        assert ids_20.issubset(ids_50)
        assert ids_50.issubset(ids_80)
        assert ids_80.issubset(ids_100)
        assert len(ids_10) < len(ids_20) < len(ids_50) < len(ids_80) <= len(ids_100)

    def test_stratified_preserves_task_groups(self):
        # 8 tasks with different numbers of groups
        entries = []
        for t in range(8):
            n_groups = (t + 1) * 3
            for g in range(n_groups):
                entries.append(
                    _make_sample(f"t{t}_g{g}", assignment=f"task_{t}", dup_group=f"t{t}_g{g}")
                )

        # Even at 0.05, every task with >=1 group must retain at least 1 group
        sub = subsample_ai_train(entries, fraction=0.05, seed=42)
        tasks_in_sub = {e.assignment for e in sub}
        assert tasks_in_sub == {f"task_{t}" for t in range(8)}

    def test_only_train_ai_is_subsampled(self):
        entries = [
            _make_sample("tr_h1", "t1", source="human", split="train"),
            _make_sample("tr_h2", "t2", source="human", split="train"),
            _make_sample("val_h1", "t1", source="human", split="val"),
            _make_sample("val_ai1", "t1", source="ai", split="val"),
            _make_sample("test_h1", "t1", source="human", split="test"),
            _make_sample("test_ai1", "t1", source="ai", split="test"),
        ]
        # Add 20 train AI entries
        for i in range(20):
            entries.append(_make_sample(f"tr_ai_{i}", f"task_{i % 2}", source="ai", split="train"))

        sub = subsample_ai_train(entries, fraction=0.10, seed=42)
        sub_ids = {e.id for e in sub}

        # Non train-AI must remain 100% intact
        assert "tr_h1" in sub_ids
        assert "tr_h2" in sub_ids
        assert "val_h1" in sub_ids
        assert "val_ai1" in sub_ids
        assert "test_h1" in sub_ids
        assert "test_ai1" in sub_ids

        # Train AI should be subsampled
        tr_ai_sub = [e for e in sub if e.source == "ai" and e.split == "train"]
        assert 0 < len(tr_ai_sub) < 20

    def test_deterministic(self):
        entries = [
            _make_sample(f"ai_{i}", f"task_{i % 3}", dup_group=f"g_{i}")
            for i in range(30)
        ]
        res1 = subsample_ai_train(entries, fraction=0.3, seed=777)
        res2 = subsample_ai_train(entries, fraction=0.3, seed=777)
        res_diff_seed = subsample_ai_train(entries, fraction=0.3, seed=888)

        assert [e.id for e in res1] == [e.id for e in res2]
        assert [e.id for e in res1] != [e.id for e in res_diff_seed]

    def test_works_on_encoded_set(self):
        samples = [
            _make_sample(f"s_{i}", f"task_{i % 2}", dup_group=f"g_{i}", source="ai" if i < 10 else "human")
            for i in range(20)
        ]
        arrays = [np.array([i, i + 1], dtype=np.uint8) for i in range(20)]
        encoded = EncodedSet.build(samples, arrays)

        sub_encoded = subsample_ai_train(encoded, fraction=0.2, seed=42)
        assert isinstance(sub_encoded, EncodedSet)
        assert len(sub_encoded) < len(encoded)

        # All 10 humans must still be present
        n_humans = sum(1 for s in sub_encoded.samples if s.source == "human")
        assert n_humans == 10

        # AI should be subsampled
        n_ai = sum(1 for s in sub_encoded.samples if s.source == "ai")
        assert 0 < n_ai < 10

        # Labels and arrays should align
        assert len(sub_encoded.samples) == len(sub_encoded.arrays) == len(sub_encoded.y)
        for s, arr, y in zip(sub_encoded.samples, sub_encoded.arrays, sub_encoded.y):
            assert y == int(s.source == "ai")
            orig_idx = int(s.id.split("_")[1])
            np.testing.assert_array_equal(arr, np.array([orig_idx, orig_idx + 1], dtype=np.uint8))


class TestTrainOptionsIntegration:
    def test_train_options_subsample_flags(self):
        from pathlib import Path
        from models.char_cnn.v2.train import TrainOptions, build_parser, options_from_args

        opts = TrainOptions(train_ai_fraction=0.4, subsample_seed=999, run_dir=Path("custom/path"))
        assert opts.train_ai_fraction == 0.4
        assert opts.subsample_seed == 999
        assert opts.run_dir == Path("custom/path")
        hp = opts.hyperparams()
        assert hp["train_ai_fraction"] == 0.4
        assert hp["subsample_seed"] == 999

    def test_train_options_rejects_invalid_fraction(self):
        from models.char_cnn.v2.train import TrainOptions

        with pytest.raises(ValueError, match="train_ai_fraction"):
            TrainOptions(train_ai_fraction=0.0)
        with pytest.raises(ValueError, match="train_ai_fraction"):
            TrainOptions(train_ai_fraction=1.1)

    def test_parser_subsample_flags(self):
        from pathlib import Path
        from models.char_cnn.v2.train import build_parser, options_from_args

        parser = build_parser()
        args = parser.parse_args([
            "--train-ai-fraction", "0.25",
            "--subsample-seed", "777",
            "--run-dir", "custom/run/dir",
            "--skip-test-eval",
            "--no-save-checkpoint",
        ])
        opts = options_from_args(args)
        assert opts.train_ai_fraction == 0.25
        assert opts.subsample_seed == 777
        assert opts.run_dir == Path("custom/run/dir")
        assert opts.skip_test_eval is True
        assert opts.keep_checkpoints is False

