"""CharCNN v2 shortcut audit: per-class shares of formatting artifacts, raw and normalized.

The audit is report-only: it is fed by the same `on_text` pass that encodes the data and must not
change any training input. CPU only, no model.
"""

import numpy as np
import pytest

from eval_factory import make_tree
from models.char_cnn.v2.data import load_views
from models.char_cnn.v2.preprocess import preprocess_v2
from models.char_cnn.v2.shortcuts import (
    LENGTH_BUCKETS,
    PATTERN_KEYS,
    SCHEMA,
    ShortcutAudit,
    hits,
    length_bucket,
    render_markdown,
)
from models.evaluation.manifest import Sample, load_manifest
from models.evaluation.splits import SplitConfig, build_split, write_manifest

CT7_KEYS = {
    "non_ascii", "course_marker", "autotest", "control", "cr", "tab", "std_prefix",
    "using_namespace", "bits_include", "non_code_first_line",
}

HUMAN = "using namespace std;\nint main() {\n    int total = 0;\n    return total;\n}\n"
AI = "#include <iostream>\nint main() {\n    int total = 0;\n    return total;\n}\n"
HUMAN_HEADED = (
    "/* Zadaća 4, Zadatak 2 - autotestovi */\r\n#include <bits/stdc++.h>\r\n"
    "int main() {\r\n\tstd::cout << \"čao\";\x0c\r\n\treturn 0;\r\n}\r\n"
)


def _sample(sample_id: str, source: str, split: str = "train") -> Sample:
    return Sample(
        id=sample_id, course="A2016", block="A/Z1", assignment="A/Z1/Z1", student=None, lang="cpp",
        source=source, model="kimi" if source == "ai" else None, profile=None, sha256="0",
        norm_hash="0", n_tokens=10, dup_group=None, dup_rep=None, cluster_id=None, gt_status=None,
        split=split, excluded=False, flags=(),
    )


def _feed(audit: ShortcutAudit, items) -> dict:
    for sample, raw in items:
        audit(sample, raw, preprocess_v2(raw))
    return audit.to_dict()


class TestPatterns:
    def test_pattern_keys_cover_ct7(self):
        assert set(PATTERN_KEYS) == CT7_KEYS

    def test_hits_on_a_headed_human_file(self):
        assert hits(HUMAN_HEADED) == CT7_KEYS - {"using_namespace"}
        assert hits(HUMAN) == {"using_namespace"}
        assert hits(AI) == set()

    def test_non_code_first_line(self):
        assert "non_code_first_line" in hits("\n\n  Ime i prezime: Neko\nint main() { return 0; }\n")
        assert "non_code_first_line" not in hits("\n#include <stdio.h>\n")
        assert "non_code_first_line" not in hits("int main() {\n")
        assert "non_code_first_line" not in hits("")

    @pytest.mark.parametrize(
        "n,bucket",
        [(0, "<512"), (511, "<512"), (512, "512-1023"), (1023, "512-1023"), (1024, "1024-2047"),
         (2047, "1024-2047"), (2048, "2048-4095"), (4095, "2048-4095"), (4096, ">=4096"), (10**6, ">=4096")],
    )
    def test_length_buckets(self, n, bucket):
        assert length_bucket(n) == bucket
        assert bucket in LENGTH_BUCKETS


class TestAudit:
    def test_using_namespace_only_in_human_files(self):
        items = [(_sample(f"h{i}.cpp", "human"), HUMAN) for i in range(3)]
        items += [(_sample(f"a{i}.cpp", "ai"), AI) for i in range(2)]
        doc = _feed(ShortcutAudit({"train": [s.id for s, _ in items]}), items)
        assert doc["schema"] == SCHEMA
        train = doc["sets"]["train"]
        assert (train["human"]["n"], train["ai"]["n"]) == (3, 2)
        for view in ("raw", "normalized"):
            assert train["human"][view]["using_namespace"] == 1.0
            assert train["ai"][view]["using_namespace"] == 0.0

    def test_every_key_for_both_classes_raw_and_normalized(self):
        items = [(_sample("h.cpp", "human"), HUMAN_HEADED), (_sample("a.cpp", "ai"), AI)]
        doc = _feed(ShortcutAudit({"train": ["h.cpp", "a.cpp"]}), items)
        for cls in ("human", "ai"):
            entry = doc["sets"]["train"][cls]
            assert set(entry["raw"]) == set(entry["normalized"]) == CT7_KEYS
            assert set(entry["length_buckets"]) == set(LENGTH_BUCKETS)

    def test_normalization_removes_the_raw_artifacts(self):
        doc = _feed(ShortcutAudit({"train": ["h.cpp"]}), [(_sample("h.cpp", "human"), HUMAN_HEADED)])
        human = doc["sets"]["train"]["human"]
        for key in ("non_ascii", "course_marker", "control", "cr", "tab", "non_code_first_line"):
            assert human["raw"][key] == 1.0, key
            assert human["normalized"][key] == 0.0, key
        for key in ("std_prefix", "bits_include"):  # real code, kept by preprocessing
            assert human["raw"][key] == human["normalized"][key] == 1.0, key

    def test_length_bucket_shares_use_normalized_length(self):
        long_text = "x = 1;\n" * 200  # 1399 normalized chars
        items = [(_sample("h1.c", "human"), HUMAN), (_sample("h2.c", "human"), long_text)]
        doc = _feed(ShortcutAudit({"train": ["h1.c", "h2.c"]}), items)
        buckets = doc["sets"]["train"]["human"]["length_buckets"]
        assert buckets["<512"] == 0.5 and buckets["1024-2047"] == 0.5
        assert sum(buckets.values()) == pytest.approx(1.0)

    def test_sets_select_samples_and_empty_classes_are_null(self):
        audit = ShortcutAudit({"train": ["h.c"], "test": ["h.c", "t.c"]})
        doc = _feed(audit, [(_sample("h.c", "human"), HUMAN), (_sample("x.c", "human"), HUMAN_HEADED),
                            (_sample("t.c", "human", "test"), AI)])
        assert doc["sets"]["train"]["human"]["n"] == 1
        assert doc["sets"]["test"]["human"]["n"] == 2
        ai = doc["sets"]["train"]["ai"]
        assert ai["n"] == 0
        assert set(ai["raw"].values()) == {None} and set(ai["length_buckets"].values()) == {None}

    def test_render_markdown_section(self):
        items = [(_sample("h.cpp", "human"), HUMAN_HEADED), (_sample("a.cpp", "ai"), AI)]
        text = render_markdown(_feed(ShortcutAudit({"train": ["h.cpp", "a.cpp"]}), items))
        assert text.startswith("## Shortcut audit")
        assert "report-only" in text
        for key in CT7_KEYS:
            assert key in text


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


def test_audit_is_report_only_on_the_data_pass(corpus):
    tree, manifest = corpus
    plain = load_views(manifest, root=tree.repo_root)
    audit = ShortcutAudit({"train": [s.id for s in manifest.samples("train", representatives_only=True)]})
    audited = load_views(manifest, root=tree.repo_root, on_text=audit)
    assert audit.to_dict()["sets"]["train"]["human"]["n"] > 0
    for name in plain:
        assert plain[name].ids == audited[name].ids
        np.testing.assert_array_equal(plain[name].y, audited[name].y)
        for a, b in zip(plain[name].arrays, audited[name].arrays):
            np.testing.assert_array_equal(a, b)
