"""Split builder: discovery, hygiene, dedup grouping, assignment and CLI on a synthetic tree."""

import json

import pytest

from eval_factory import MODELS, PROFILES, make_tree
from models.evaluation.splits import (
    ENTRY_KEYS,
    SplitConfig,
    build_split,
    hygiene_flags,
    parse_path,
    scan,
)


def _config(tree, seed=7, **overrides):
    return SplitConfig(
        seed=seed,
        repo_root=tree.repo_root,
        raw_root=tree.raw_root,
        ai_root=tree.ai_root,
        gt_static=tree.gt_static,
        gt_ambiguous=(tree.gt_dynamic,),
        **overrides,
    )


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tree = make_tree(tmp_path_factory.mktemp("corpus"))
    before = _snapshot(tree.repo_root)
    manifest = build_split(_config(tree))
    return tree, manifest, before


@pytest.fixture(scope="module")
def entries(built):
    return {e["id"]: e for e in built[1]["entries"]}


# --- discovery (DS1.1-1.4, DS2.2) -------------------------------------------------------------


class TestDiscovery:
    def test_every_entry_carries_every_key_with_null_for_not_applicable(self, entries):
        assert entries
        for entry in entries.values():
            assert set(ENTRY_KEYS) <= set(entry), entry["id"]
        human = entries["data/raw/src/A2016/Z1/Z1/student1001.c"]
        assert human["source"] == "human" and human["lang"] == "c"
        assert human["model"] is None and human["profile"] is None
        assert human["course"] == "A2016" and human["block"] == "A/Z1"
        assert human["assignment"] == "A2016/Z1/Z1" and human["student"] == "student1001"

    def test_ai_metadata_is_parsed_from_the_filename(self, entries):
        ai = [e for e in entries.values() if e["source"] == "ai" and "unparsed_name" not in e["flags"]]
        assert ai
        for entry in ai:
            assert entry["model"] in MODELS and entry["profile"] in PROFILES
            assert entry["student"] is None
        cpp = [e for e in ai if e["lang"] == "cpp"]
        assert cpp and all(e["course"].startswith("B") for e in cpp)

    def test_unparseable_ai_name_is_kept_with_flag(self, built, entries):
        weird = entries[built[0].ids["weird_ai"]]
        assert "unparsed_name" in weird["flags"]
        assert weird["model"] is None and weird["profile"] is None
        assert "broken" not in weird["flags"]

    def test_ids_are_sorted_repo_relative_posix_paths(self, built):
        tree, manifest, _ = built
        ids = [e["id"] for e in manifest["entries"]]
        assert ids == sorted(ids)
        assert all(i.startswith(("data/raw/src/", "data/output/")) for i in ids)
        assert str(tree.repo_root) not in json.dumps(manifest)
        assert tree.repo_root.as_posix() not in json.dumps(manifest)

    def test_every_file_on_disk_is_discovered(self, built):
        tree, manifest, before = built
        on_disk = {p for p in before if p.endswith((".c", ".cpp"))}
        assert {e["id"] for e in manifest["entries"]} == on_disk

    def test_config_and_stats_are_present(self, built):
        config, stats = built[1]["config"], built[1]["stats"]
        assert config["seed"] == 7
        assert config["dedup"]["threshold"] == 0.85
        assert config["dedup"]["shingle_k"] == 5
        assert config["hygiene"]["min_effective_bytes"] == 50
        assert config["roots"] == {"raw": "data/raw/src", "ai": "data/output"}
        assert config["builder_version"]
        assert {"test", "val"} <= set(config["fractions"]["target"])
        assert stats and built[1]["schema"] == "graphito.split/v1"

    def test_source_files_are_untouched(self, built):
        tree, _, before = built
        assert _snapshot(tree.repo_root) == before

    def test_roots_are_overridable(self, tmp_path):
        tree = make_tree(tmp_path / "elsewhere", n_blocks=4, planted=False)
        files = scan(tree.raw_root, tree.ai_root, tree.repo_root)
        assert files and all(f.id.startswith("data/") for f in files)
        assert [f.id for f in files] == sorted(f.id for f in files)

    def test_root_outside_repo_root_raises(self, tmp_path):
        tree = make_tree(tmp_path / "a", n_blocks=4, planted=False)
        with pytest.raises(ValueError, match="repo_root"):
            scan(tree.raw_root, tree.ai_root, tmp_path / "b")

    def test_parse_path(self):
        ai = parse_path("B2016/Z2/Z1/ref_comentado-basic_or-kimi_20260714_200817_0002.cpp", "ai")
        assert ai["course"] == "B2016" and ai["block"] == "B/Z2"
        assert ai["assignment"] == "B2016/Z2/Z1" and ai["lang"] == "cpp"
        assert (ai["profile"], ai["model"], ai["student"]) == ("comentado-basic", "kimi", None)
        human = parse_path("A2017/Z3/Z2/student42 (1).c", "human")
        assert human["student"] == "student42" and human["lang"] == "c"
        with pytest.raises(ValueError, match="layout"):
            parse_path("A2016/student1.c", "human")


# --- hygiene and dedup (DS2.1-2.5) -------------------------------------------------------------


class TestHygieneDedup:
    @pytest.mark.parametrize(
        "name, sub_flag",
        [("empty", "empty"), ("too_short", "too_short"), ("comment_only", "too_short"),
         ("copy_suffix", "copy_suffix")],
    )
    def test_broken_files_are_flagged_kept_and_ungrouped(self, built, entries, name, sub_flag):
        entry = entries[built[0].ids[name]]
        assert "broken" in entry["flags"] and sub_flag in entry["flags"]
        assert entry["excluded"] is True
        assert entry["dup_group"] is None and entry["cluster_id"] is None

    def test_copy_suffix_without_student_id_gets_both_sub_flags(self, built, entries):
        flags = entries[built[0].ids["copy_suffix"]]["flags"]
        assert {"broken", "copy_suffix", "no_student_id"} <= set(flags)

    def test_hygiene_flags_unit(self):
        code = b"int main(void) { int a = 1, b = 2; return a + b * 3 - (a << 2) + (b >> 1); }"
        assert hygiene_flags("student1.c", code, "human", "student1") == []
        assert hygiene_flags("student1.c", b"", "human", "student1") == ["broken", "empty"]
        assert hygiene_flags("x.c", code, "human", None) == ["broken", "no_student_id"]
        assert hygiene_flags("ref_x.c", code, "ai", None) == []  # AI files carry no student id
        assert hygiene_flags("s (2).c", code, "human", "s") == ["broken", "copy_suffix"]

    def test_comment_whitespace_rename_pair_shares_a_dup_group(self, built, entries):
        a, b = entries[built[0].ids["near_a"]], entries[built[0].ids["near_b"]]
        assert a["norm_hash"] != b["norm_hash"]
        assert a["dup_group"] == b["dup_group"] is not None
        assert a["dup_rep"] == b["dup_rep"] == min(a["id"], b["id"])
        assert a["dup_group"].startswith("dg-") and len(a["dup_group"]) == 13

    def test_identical_files_across_blocks_share_one_exact_group(self, built, entries):
        ids = [v for k, v in built[0].ids.items() if k.startswith("cross_exact_")]
        groups = {entries[i]["dup_group"] for i in ids}
        assert len(groups) == 1 and None not in groups
        assert len({entries[i]["block"] for i in ids}) == len(ids)

    def test_cross_block_near_dups_are_counted_not_merged(self, built, entries):
        a, b = entries[built[0].ids["cross_near_a"]], entries[built[0].ids["cross_near_b"]]
        assert a["block"] != b["block"]
        assert a["dup_group"] != b["dup_group"]
        stats = built[1]["stats"]
        assert stats["cross_block_dup_groups"] >= 2  # the exact group and the near pair
        assert stats["dedup"]["cross_block_near_pairs"] >= 1

    def test_threshold_sensitivity_is_monotone_and_matches_operative_groups(self, built, entries):
        sens = built[1]["stats"]["dup_threshold_sensitivity"]
        assert set(sens) == {"0.80", "0.85", "0.90"}
        assert sens["0.80"] < sens["0.85"] < sens["0.90"]  # planted pairs separate thresholds
        live = {e["dup_group"] for e in entries.values() if "broken" not in e["flags"]}
        assert None not in live
        assert sens["0.85"] == len(live)

    def test_mid_pair_is_merged_and_low_pair_is_not_at_operative_threshold(self, built, entries):
        ids = built[0].ids
        assert entries[ids["near_mid_a"]]["dup_group"] == entries[ids["near_mid_b"]]["dup_group"]
        assert entries[ids["near_low_a"]]["dup_group"] != entries[ids["near_low_b"]]["dup_group"]

    def test_dup_group_ids_are_stable_when_unrelated_files_are_added(self, tmp_path):
        tree = make_tree(tmp_path, n_blocks=6)
        first = {e["id"]: e["dup_group"] for e in build_split(_config(tree))["entries"]}
        extra = tree.raw_root / "A2016" / "Z6" / "Z1" / "student1888.c"
        extra.write_text("int main(void) { int q = 4; while (q > 0) { q = q - 1; } return q * 7; }\n")
        second = {e["id"]: e["dup_group"] for e in build_split(_config(tree))["entries"]}
        assert all(second[i] == g for i, g in first.items())
