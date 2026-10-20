"""Tests for the leave-one-LLM-out helpers (models.char_cnn.v2.lolo) and their trainer wiring."""

from dataclasses import dataclass
from typing import List, Optional

import pytest

from models.char_cnn.v2 import lolo
from models.char_cnn.v2.train import TrainOptions, build_parser, options_from_args


@dataclass(frozen=True)
class S:
    id: str
    source: str
    model: Optional[str]
    split: str
    dup_group: Optional[str]
    assignment: str


def _corpus() -> List[S]:
    rows: List[S] = []
    n = 0
    for split in ("train", "val", "test"):
        for k in range(6):
            rows.append(S(f"h-{split}-{k}", "human", None, split, f"hg-{split}-{k}", "A1"))
        for model, count in (("deepseek-chat", 12), ("qwen3", 6), ("kimi", 1)):
            for k in range(count):
                n += 1
                task = f"T{k % 3}"
                # every other file of deepseek shares its dup_group with the previous one
                grp = f"g-{split}-{model}-{k // 2 if model == 'deepseek-chat' else k}"
                rows.append(S(f"{model}-{split}-{k}", "ai", model, split, grp, task))
    return rows


def _ai(entries, model, split):
    return [e for e in entries if e.source == "ai" and e.model == model and e.split == split]


def test_restrict_keeps_humans_untouched():
    data = _corpus()
    out = lolo.restrict_ai_models(data, {"deepseek-chat"})
    assert [e for e in out if e.source == "human"] == [e for e in data if e.source == "human"]


def test_restrict_keeps_only_allowed_ai_in_train_and_val():
    out = lolo.restrict_ai_models(_corpus(), {"deepseek-chat"})
    for split in ("train", "val"):
        assert {e.model for e in out if e.source == "ai" and e.split == split} == {"deepseek-chat"}
    assert len(_ai(out, "deepseek-chat", "train")) == 12


def test_restrict_never_leaks_other_generators():
    out = lolo.restrict_ai_models(_corpus(), {"qwen3"})
    leaked = [e for e in out if e.source == "ai" and e.split in ("train", "val") and e.model != "qwen3"]
    assert leaked == []


def test_restrict_leaves_other_splits_alone():
    data = _corpus()
    out = lolo.restrict_ai_models(data, {"qwen3"}, splits=("train", "val"))
    assert [e for e in out if e.split == "test"] == [e for e in data if e.split == "test"]


def test_restrict_rejects_empty_allowed_set():
    with pytest.raises(ValueError):
        lolo.restrict_ai_models(_corpus(), set())


def test_count_ai_groups_counts_unique_dup_groups():
    data = _corpus()
    assert lolo.count_ai_groups(data, "deepseek-chat", "train") == 6
    assert lolo.count_ai_groups(data, "qwen3", "train") == 6
    assert lolo.count_ai_groups(data, "absent", "train") == 0


def test_match_hits_exact_group_count_and_keeps_groups_whole():
    data = lolo.restrict_ai_models(_corpus(), {"deepseek-chat"})
    out = lolo.match_ai_groups(data, target_groups=4, seed=42)
    assert lolo.count_ai_groups(out, "deepseek-chat", "train") == 4
    kept = {e.dup_group for e in _ai(out, "deepseek-chat", "train")}
    for e in _ai(data, "deepseek-chat", "train"):
        assert (e.dup_group in kept) == (e in out)


def test_match_is_deterministic_and_seed_sensitive():
    data = lolo.restrict_ai_models(_corpus(), {"deepseek-chat"})
    a = lolo.match_ai_groups(data, 3, seed=1)
    b = lolo.match_ai_groups(data, 3, seed=1)
    assert a == b
    assert any(lolo.match_ai_groups(data, 3, seed=s) != a for s in range(2, 12))


def test_match_leaves_humans_val_and_test_intact():
    data = lolo.restrict_ai_models(_corpus(), {"deepseek-chat"})
    out = lolo.match_ai_groups(data, 2, seed=7)
    assert [e for e in out if e.split != "train" or e.source == "human"] == [
        e for e in data if e.split != "train" or e.source == "human"
    ]


def test_match_is_stratified_by_assignment():
    data = lolo.restrict_ai_models(_corpus(), {"deepseek-chat"})
    out = lolo.match_ai_groups(data, 3, seed=5)
    tasks = {e.assignment for e in _ai(out, "deepseek-chat", "train")}
    assert tasks == {"T0", "T1", "T2"}  # 3 groups over 3 tasks: one each (proportional quotas)


def test_match_rejects_target_above_availability():
    data = lolo.restrict_ai_models(_corpus(), {"deepseek-chat"})
    with pytest.raises(ValueError):
        lolo.match_ai_groups(data, 99, seed=1)


def test_partition_by_generator_groups_test_entries():
    parts = lolo.partition_by_generator([e for e in _corpus() if e.split == "test"])
    assert set(parts) == {"human", "deepseek-chat", "qwen3", "kimi"}
    assert len(parts["human"]) == 6 and len(parts["deepseek-chat"]) == 12 and len(parts["qwen3"]) == 6
    assert all(e.source == "human" for e in parts["human"])


def test_trainer_defaults_leave_lolo_off():
    opts = options_from_args(build_parser().parse_args([]))
    assert opts.train_ai_models == ()
    assert opts.match_ai_groups_to is None
    assert "train_ai_models" not in opts.hyperparams()  # default config.json stays identical


def test_trainer_flags_are_parsed_and_recorded():
    args = build_parser().parse_args(
        ["--train-ai-models", "deepseek-chat", "--match-ai-groups-to", "qwen3"]
    )
    opts = options_from_args(args)
    assert opts.train_ai_models == ("deepseek-chat",)
    assert opts.match_ai_groups_to == "qwen3"
    assert opts.hyperparams()["train_ai_models"] == ["deepseek-chat"]


def test_match_requires_models_option():
    with pytest.raises(ValueError):
        TrainOptions(match_ai_groups_to="qwen3")
