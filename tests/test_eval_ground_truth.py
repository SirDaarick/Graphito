"""Ground-truth parsing, cluster resolution against files on disk, and labelled pairs."""

import pytest

from models.evaluation.ground_truth import (
    HumanFile,
    pairs,
    parse_ground_truth,
    resolve_clusters,
)

GT_TEXT = """\
- A2016/Z1/Z1
student1,student2
student3,student4
- A2016/Z1/Z2
student1,student5

student5,student6
student7,student8
"""


def _write_gt(tmp_path, text=GT_TEXT, name="gt-static.txt"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _file(assignment, student, excluded=False):
    return HumanFile(f"data/raw/src/{assignment}/{student}.c", assignment, student, excluded)


@pytest.fixture
def files():
    z1 = [_file("A2016/Z1/Z1", f"student{i}") for i in (1, 2, 3, 4, 9)]
    # student8 (listed in the ground truth with student7) has no file on disk
    z2 = [_file("A2016/Z1/Z2", f"student{i}") for i in (1, 5, 6, 7, 9)]
    b2017 = [_file("B2017/Z1/Z1", f"student{i}") for i in (1, 2)]
    return z1 + z2 + b2017


def test_parse_ground_truth_groups_lines_per_assignment(tmp_path):
    gt = parse_ground_truth(_write_gt(tmp_path))
    assert gt == {
        "A2016/Z1/Z1": [{"student1", "student2"}, {"student3", "student4"}],
        "A2016/Z1/Z2": [{"student1", "student5"}, {"student5", "student6"}, {"student7", "student8"}],
    }


def test_parse_ground_truth_rejects_cluster_line_before_header(tmp_path):
    with pytest.raises(ValueError, match="before any"):
        parse_ground_truth(_write_gt(tmp_path, "student1,student2\n- A2016/Z1/Z1\n"))


def test_clusters_are_resolved_per_assignment_with_deterministic_ids(tmp_path, files):
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)

    assert sorted(res.clusters) == [
        "A2016/Z1/Z1#01",
        "A2016/Z1/Z1#02",
        "A2016/Z1/Z2#01",
        "A2016/Z1/Z2#02",
    ]
    z1_first = res.clusters["A2016/Z1/Z1#01"]
    assert z1_first.students == ("student1", "student2")
    assert z1_first.members == (
        "data/raw/src/A2016/Z1/Z1/student1.c",
        "data/raw/src/A2016/Z1/Z1/student2.c",
    )
    assert res.cluster_of["data/raw/src/A2016/Z1/Z1/student3.c"] == "A2016/Z1/Z1#02"
    assert "data/raw/src/A2016/Z1/Z1/student9.c" not in res.cluster_of


def test_student_in_two_lines_merges_them_into_one_cluster(tmp_path, files):
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)

    merged = res.clusters["A2016/Z1/Z2#01"]
    assert merged.students == ("student1", "student5", "student6")
    assert res.merged_lines == 1  # three Z2 lines collapse into two clusters
    ids = {res.cluster_of[f"data/raw/src/A2016/Z1/Z2/student{i}.c"] for i in (1, 5, 6)}
    assert ids == {"A2016/Z1/Z2#01"}
    assert "smallest student id" in res.rule


def test_cluster_numbering_does_not_depend_on_line_order(tmp_path, files):
    reordered = "- A2016/Z1/Z1\nstudent3,student4\nstudent1,student2\n"
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path, reordered)), files)
    assert res.cluster_of["data/raw/src/A2016/Z1/Z1/student1.c"] == "A2016/Z1/Z1#01"
    assert res.cluster_of["data/raw/src/A2016/Z1/Z1/student3.c"] == "A2016/Z1/Z1#02"


def test_student_cluster_links_span_assignments(tmp_path, files):
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)
    assert res.student_clusters["student1"] == ["A2016/Z1/Z1#01", "A2016/Z1/Z2#01"]
    assert "student9" not in res.student_clusters  # never listed in the ground truth


def test_missing_file_goes_to_unresolved_not_to_members(tmp_path, files):
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)

    assert res.unresolved == [
        {
            "cluster": "A2016/Z1/Z2#02",
            "assignment": "A2016/Z1/Z2",
            "student": "student8",
            "reason": "no_file",
        }
    ]
    cluster = res.clusters["A2016/Z1/Z2#02"]
    assert cluster.members == ("data/raw/src/A2016/Z1/Z2/student7.c",)
    assert cluster.unresolved == ("student8",)
    assert not any("student8" in sid for sid in res.gt_status)


def test_excluded_files_are_unresolved_and_not_labelled(tmp_path, files):
    files = [f._replace(excluded=True) if f.student == "student6" else f for f in files]
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)

    reasons = {(u["student"], u["reason"]) for u in res.unresolved}
    assert ("student6", "excluded") in reasons
    assert "data/raw/src/A2016/Z1/Z2/student6.c" not in res.gt_status
    assert "data/raw/src/A2016/Z1/Z2/student6.c" not in res.cluster_of


def test_course_absent_from_ground_truth_is_unlabeled(tmp_path, files):
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)

    assert res.unlabeled_courses == ["B2017"]
    assert res.gt_status["data/raw/src/B2017/Z1/Z1/student1.c"] == "unlabeled"
    assert "data/raw/src/B2017/Z1/Z1/student1.c" not in res.cluster_of
    assert res.gt_status["data/raw/src/A2016/Z1/Z1/student1.c"] == "positive"
    assert res.gt_status["data/raw/src/A2016/Z1/Z1/student9.c"] == "negative"


def test_students_only_in_dynamic_ground_truth_are_ambiguous(tmp_path, files):
    static = parse_ground_truth(_write_gt(tmp_path))
    dynamic = parse_ground_truth(
        _write_gt(tmp_path, "- A2016/Z1/Z1\nstudent1,student9\n", name="gt-dynamic.txt")
    )
    res = resolve_clusters(static, files, ambiguous_gt=dynamic)

    assert res.gt_status["data/raw/src/A2016/Z1/Z1/student9.c"] == "ambiguous"
    assert res.gt_status["data/raw/src/A2016/Z1/Z1/student1.c"] == "positive"  # static wins
    assert res.gt_status["data/raw/src/A2016/Z1/Z2/student9.c"] == "negative"  # other assignment


def test_pairs_label_same_cluster_as_positive(tmp_path, files):
    res = resolve_clusters(parse_ground_truth(_write_gt(tmp_path)), files)
    labelled = list(pairs(res))

    z1 = [(a, b, y) for a, b, y in labelled if "/Z1/Z1/" in a]
    z2 = [(a, b, y) for a, b, y in labelled if "/Z1/Z2/" in a]
    assert len(z1) == 10 and sum(y for *_, y in z1) == 2
    assert len(z2) == 10 and sum(y for *_, y in z2) == 3
    assert ("data/raw/src/A2016/Z1/Z1/student1.c", "data/raw/src/A2016/Z1/Z1/student2.c", 1) in z1
    assert ("data/raw/src/A2016/Z1/Z1/student1.c", "data/raw/src/A2016/Z1/Z1/student3.c", 0) in z1
    assert not any("B2017" in a for a, _, _ in labelled)  # unlabeled course never yields pairs
    assert labelled == sorted(labelled, key=lambda t: (res.assignment_of[t[0]], t[0], t[1]))
    assert all(a < b for a, b, _ in labelled)


def test_pairs_skip_ambiguous_unless_requested_and_honour_id_filter(tmp_path, files):
    static = parse_ground_truth(_write_gt(tmp_path))
    dynamic = parse_ground_truth(
        _write_gt(tmp_path, "- A2016/Z1/Z1\nstudent1,student9\n", name="gt-dynamic.txt")
    )
    res = resolve_clusters(static, files, ambiguous_gt=dynamic)

    assert len([p for p in pairs(res) if "/Z1/Z1/" in p[0]]) == 6  # 4 labelled files
    assert len([p for p in pairs(res, include_ambiguous=True) if "/Z1/Z1/" in p[0]]) == 10

    keep = {
        "data/raw/src/A2016/Z1/Z1/student1.c",
        "data/raw/src/A2016/Z1/Z1/student2.c",
        "data/raw/src/A2016/Z1/Z1/student3.c",
    }
    assert [y for *_, y in pairs(res, ids=keep)] == [1, 0, 0]


def test_same_student_files_never_form_a_pair(tmp_path):
    gt = parse_ground_truth(_write_gt(tmp_path, "- A2016/Z1/Z1\nstudent1,student2\n"))
    files = [
        HumanFile("a/student1.c", "A2016/Z1/Z1", "student1"),
        HumanFile("a/student1.cpp", "A2016/Z1/Z1", "student1"),
        HumanFile("a/student2.c", "A2016/Z1/Z1", "student2"),
    ]
    res = resolve_clusters(gt, files)
    assert {frozenset(p[:2]) for p in pairs(res)} == {
        frozenset({"a/student1.c", "a/student2.c"}),
        frozenset({"a/student1.cpp", "a/student2.c"}),
    }
