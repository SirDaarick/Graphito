"""Split builder: discovery, hygiene, dedup grouping, assignment and CLI on a synthetic tree."""

import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval_factory import MODELS, PROFILES, make_tree
from models.evaluation.splits import (
    ENTRY_KEYS,
    MIN_EFFECTIVE_BYTES,
    SPLITS,
    SplitConfig,
    build_split,
    dumps_manifest,
    hygiene_flags,
    parse_path,
    scan,
    validate,
    write_manifest,
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

    def test_min_effective_bytes_default_is_shared(self):
        default = inspect.signature(hygiene_flags).parameters["min_effective_bytes"].default
        assert default == SplitConfig().min_effective_bytes == MIN_EFFECTIVE_BYTES

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


# --- assignment (DS3.1-3.9) --------------------------------------------------------------------


def _by(entries, key, included_only=False):
    out = {}
    for e in entries.values():
        if e[key] is None or (included_only and e["excluded"]):
            continue
        out.setdefault(e[key], set()).add(e["split"])
    return out


class TestAssignment:
    def test_rebuild_with_same_seed_is_byte_identical(self, tmp_path):
        tree = make_tree(tmp_path / "corpus")
        first, second, other = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "c.json"
        write_manifest(build_split(_config(tree, seed=7)), first)
        write_manifest(build_split(_config(tree, seed=7)), second)
        assert first.read_bytes() == second.read_bytes()
        reseeded = build_split(_config(tree, seed=8))
        validate(reseeded)
        write_manifest(reseeded, other)
        assert json.loads(other.read_text(encoding="utf-8"))["config"]["seed"] == 8

    def test_parallel_file_analysis_matches_serial(self, tmp_path):
        tree = make_tree(tmp_path / "corpus", n_blocks=5)
        serial = dumps_manifest(build_split(_config(tree, workers=1)))
        parallel = dumps_manifest(build_split(_config(tree, workers=2)))
        assert parallel == serial

    def test_manifest_file_is_lf_sorted_and_one_entry_per_line(self, built, tmp_path):
        tree, manifest, _ = built
        path = tmp_path / "split.json"
        write_manifest(manifest, path)
        data = path.read_bytes()
        assert b"\r" not in data and data.endswith(b"\n")
        assert json.loads(data.decode("utf-8")) == json.loads(json.dumps(manifest))
        lines = data.decode("utf-8").splitlines()
        entry_lines = [ln for ln in lines if ln.startswith('{"assignment":')]
        assert len(entry_lines) == len(manifest["entries"])
        assert list(json.loads(data)) == sorted(manifest)
        assert dumps_manifest(manifest) == data.decode("utf-8")
        assert tree.repo_root.as_posix() not in data.decode("utf-8")

    def test_write_manifest_failure_leaves_previous_file_and_no_temp(self, built, tmp_path, monkeypatch):
        path = tmp_path / "out" / "split.json"
        path.parent.mkdir()
        path.write_bytes(b"previous manifest\n")
        real_write = Path.write_bytes

        def torn_write(self, data):  # simulate a crash halfway through the write
            real_write(self, data[: len(data) // 2])
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_bytes", torn_write)
        with pytest.raises(OSError, match="disk full"):
            write_manifest(built[1], path)
        monkeypatch.undo()
        assert path.read_bytes() == b"previous manifest\n"
        assert [p.name for p in path.parent.iterdir()] == ["split.json"]
        write_manifest(built[1], path)
        assert path.read_bytes() == dumps_manifest(built[1]).encode("utf-8")
        assert [p.name for p in path.parent.iterdir()] == ["split.json"]

    def test_one_split_per_block_dup_group_and_cluster(self, entries):
        assert all(e["split"] in SPLITS for e in entries.values())
        for key, included in (("block", False), ("dup_group", True), ("cluster_id", False)):
            spans = {k: v for k, v in _by(entries, key, included).items() if len(v) > 1}
            assert not spans, (key, spans)

    def test_blocks_section_maps_every_block_to_its_split(self, built, entries):
        blocks = built[1]["blocks"]
        assert sorted(blocks) == [f"{L}/Z{z}" for L in "AB" for z in range(1, 7)]
        assert blocks["A/Z1"]["courses"] == ["A2016", "A2017"]
        for block, info in blocks.items():
            members = [e for e in entries.values() if e["block"] == block]
            assert info["n_samples"] == len(members)
            assert {e["split"] for e in members} == {info["split"]}

    def test_test_and_val_get_at_least_two_blocks_and_fractions_are_recorded(self, built):
        manifest = built[1]
        for letter in "AB":
            splits = [v["split"] for k, v in manifest["blocks"].items() if k.startswith(letter)]
            assert splits.count("test") >= 2 and splits.count("val") >= 2
            assert splits.count("train") >= 1
            actual = manifest["config"]["fractions"]["actual"][letter]
            assert actual == manifest["stats"]["blocks"][letter]
            assert actual["n_blocks"] == 6 and actual["test"] == splits.count("test")
            assert actual["test_fraction"] == round(splits.count("test") / 6, 6)
        assert manifest["config"]["attempt"] >= 0

    def test_cross_block_dup_is_pinned_to_most_held_out_split(self, built, entries):
        ids = [v for k, v in built[0].ids.items() if k.startswith("cross_exact_")]
        members = [entries[i] for i in ids]
        assert {m["split"] for m in members} == {"train", "val", "test"}  # spans all of course A
        for m in members:
            if m["split"] == "test":
                assert not m["excluded"] and "cross_split_dup" not in m["flags"]
            else:
                assert m["excluded"] and "cross_split_dup" in m["flags"]
        dedup = built[1]["stats"]["dedup"]
        assert dedup["pinned_exclusions"] == sum(m["split"] != "test" for m in members) == 4
        assert dedup["pinned_groups"] >= 1

    def test_unresolved_member_is_in_stats_and_not_in_entries(self, built, entries):
        unresolved = built[1]["stats"]["unresolved_cluster_members"]
        assert {"assignment": "A2016/Z2/Z1", "cluster": "A2016/Z2/Z1#02", "reason": "no_file",
                "student": "student1999"} in unresolved
        assert not any("student1999" in i for i in entries)

    def test_overlapping_gt_lines_share_one_cluster(self, built, entries):
        ids = built[0].ids
        assert entries[ids["gt_overlap_a"]]["cluster_id"] == "A2016/Z1/Z1#01"
        assert entries[ids["gt_overlap_b"]]["cluster_id"] == "A2016/Z1/Z1#01"
        assert built[1]["config"]["ground_truth"]["cluster_id_rule"]
        assert "header" in built[1]["config"]["ground_truth"]["label_rule"]

    def test_course_without_gt_is_unlabeled_with_null_cluster(self, entries):
        b2017 = [e for e in entries.values() if e["course"] == "B2017" and e["source"] == "human"]
        assert b2017
        assert all(e["cluster_id"] is None and e["gt_status"] == "unlabeled" for e in b2017)
        unheaded = [e for e in entries.values() if e["assignment"] == "A2017/Z6/Z1" and e["source"] == "human"]
        assert unheaded and all(e["gt_status"] == "unlabeled" for e in unheaded)
        assert all(e["gt_status"] == "n/a" for e in entries.values() if e["source"] == "ai")

    def test_student_clusters_in_several_splits_are_reported(self, built):
        # student1001 is clustered in every A2016 assignment, so its clusters span splits; the
        # link is reported as overlap instead of merging blocks (see tasks.md WU4 evidence).
        gt = built[1]["stats"]["gt"]
        assert gt["cross_split_student_clusters"] >= 1
        assert sum(gt["clusters_by_split"].values()) == len(built[1]["groups"]["clusters"])

    def test_three_block_course_raises_on_two_block_minimum(self, tmp_path):
        tree = make_tree(tmp_path, n_blocks=3, planted=False)
        with pytest.raises(ValueError, match="2-block minimum"):
            build_split(_config(tree))

    def test_unfillable_stratum_raises_naming_it(self, tmp_path):
        tree = make_tree(tmp_path, lang_b="c", cpp_blocks=1, planted=False)
        with pytest.raises(ValueError, match="lang=cpp"):
            build_split(_config(tree))

    def test_student_overlap_is_reported_without_error(self, built):
        overlap = built[1]["stats"]["student_overlap"]
        assert overlap["overall"]["n_multi_split"] >= 1
        assert set(overlap["overall"]) == {"n_multi_split", "train-val", "train-test", "val-test"}
        assert set(overlap["by_letter"]) == {"A", "B"}

    def test_every_split_has_both_langs_and_sources(self, built):
        counts = built[1]["stats"]["counts"]
        for split in SPLITS:
            assert set(counts[split]) == {"human", "ai"}
            langs = {lang for by_lang in counts[split].values() for lang in by_lang}
            assert langs == {"c", "cpp"}

    def test_validate_rejects_a_block_spanning_splits(self, built):
        manifest = json.loads(json.dumps(built[1]))
        entry = next(e for e in manifest["entries"] if e["block"] == "A/Z1")
        entry["split"] = next(s for s in SPLITS if s != entry["split"])
        with pytest.raises(ValueError, match="block"):
            validate(manifest)

    def test_negative_near_dups_are_listed_in_gt_stats(self, built):
        ids = built[0].ids
        neg = built[1]["stats"]["gt"]["negative_near_dup"]
        assert [ids["near_a"], ids["near_b"]] in neg["pairs"]
        assert sum(neg["by_split"].values()) == len(neg["pairs"])

    def test_dup_group_size_distribution(self, built):
        sizes = built[1]["stats"]["dedup"]["size_distribution"]
        assert sizes["6"] == 1  # the cross-block exact group
        assert built[1]["groups"]["dup"]
        cross = [g for g in built[1]["groups"]["dup"].values() if g["cross_block"]]
        assert any(g["kind"] == "exact" and len(g["blocks"]) == 6 for g in cross)

# --- CLI (scripts/build_split.py) --------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_split.py"


def _cli(tree, out, *extra):
    cmd = [
        sys.executable, str(SCRIPT), "--seed", "7", "--repo-root", str(tree.repo_root),
        "--raw-root", str(tree.raw_root), "--ai-root", str(tree.ai_root),
        "--gt-static", str(tree.gt_static), "--gt-ambiguous", str(tree.gt_dynamic),
        "--out", str(out), *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(out.parent.parent))


class TestCli:
    def test_cli_writes_the_same_manifest_as_the_library(self, tmp_path):
        tree = make_tree(tmp_path / "corpus")
        out = tmp_path / "out" / "split.json"
        proc = _cli(tree, out)
        assert proc.returncode == 0, proc.stderr
        assert out.read_bytes() == dumps_manifest(build_split(_config(tree))).encode("utf-8")
        for stage in ("scan", "read_normalize", "dedup", "assign", "total"):
            assert stage in proc.stdout
        assert hashlib.sha256(out.read_bytes()).hexdigest() in proc.stdout

    def test_cli_reports_builder_errors_with_non_zero_exit(self, tmp_path):
        tree = make_tree(tmp_path / "corpus", n_blocks=3, planted=False)
        out = tmp_path / "out" / "split.json"
        proc = _cli(tree, out)
        assert proc.returncode != 0
        assert "2-block minimum" in proc.stderr
        assert not out.exists()