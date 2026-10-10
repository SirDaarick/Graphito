"""Plagiarism ground truth: parsing, cluster resolution against files on disk, labelled pairs.

File format (`data/raw/ground-truth-*-anon.txt`): a header `- <course>/<Zx>/<Zy>` followed by one
line per plagiarism group, with comma-separated anonymised student ids.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, NamedTuple, Optional, Set, Tuple

from .dedup import UnionFind

_HEADER_RE = re.compile(r"^-\s+(\S+)$")

CLUSTER_ID_RULE = (
    "GT lines that share a student inside one assignment are merged into one cluster; clusters "
    "are numbered from 01 per assignment in ascending order of smallest student id, as "
    "<assignment>#NN"
)

LABEL_RULE = (
    "positive = member of a static cluster; ambiguous = listed only in the dynamic/full ground "
    "truth of that assignment; negative = any other file of an assignment with a static header; "
    "unlabeled = course without ground truth or assignment without a static header (the dataset "
    "readme does not guarantee that unheaded assignments were inspected)"
)


class HumanFile(NamedTuple):
    """A human submission on disk. `excluded` files (broken, ...) never join a cluster."""

    id: str
    assignment: str  # e.g. "A2016/Z1/Z1"
    student: str
    excluded: bool = False


@dataclass(frozen=True)
class Cluster:
    id: str
    assignment: str
    students: Tuple[str, ...]  # every student listed in the ground truth, on disk or not
    members: Tuple[str, ...]  # sample ids resolved on disk
    unresolved: Tuple[str, ...]  # students without a usable file


@dataclass(frozen=True)
class Resolution:
    clusters: Dict[str, Cluster]  # only clusters with at least one resolved member
    cluster_of: Dict[str, str]  # sample id -> cluster id
    gt_status: Dict[str, str]  # sample id -> positive | negative | ambiguous | unlabeled
    assignment_of: Dict[str, str]
    student_of: Dict[str, str]
    student_clusters: Dict[str, List[str]]  # student -> cluster ids (links clusters across assignments)
    unresolved: List[Dict[str, str]]  # {cluster, assignment, student, reason: no_file | excluded}
    merged_lines: int  # GT lines absorbed by another line sharing a student
    unlabeled_courses: List[str]  # courses on disk with no ground truth at all
    unlabeled_assignments: List[str]  # assignments of labelled courses without a static header
    rule: str = CLUSTER_ID_RULE
    label_rule: str = LABEL_RULE


def parse_ground_truth(path: "str | Path") -> Dict[str, List[Set[str]]]:
    """Parse a ground-truth file into {assignment: [set of students per line]}."""
    out: Dict[str, List[Set[str]]] = {}
    current: Optional[str] = None
    text = Path(path).read_text(encoding="utf-8-sig")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        header = _HEADER_RE.match(line)
        if header:
            current = header.group(1)
            out.setdefault(current, [])
            continue
        if current is None:
            raise ValueError(f"{path}:{lineno}: cluster line before any '- <assignment>' header")
        members = {s.strip() for s in line.split(",") if s.strip()}
        if members:
            out[current].append(members)
    return out


def _course(assignment: str) -> str:
    return assignment.split("/", 1)[0]


def resolve_clusters(
    gt: Mapping[str, List[Set[str]]],
    files: Iterable[HumanFile],
    ambiguous_gt: Optional[Mapping[str, List[Set[str]]]] = None,
) -> Resolution:
    """Resolve static ground-truth clusters against the human files on disk.

    `ambiguous_gt` (dynamic/full ground truth) only marks students absent from the static
    clusters of that assignment as `ambiguous`. Excluded files are never labelled; a student
    whose files are all excluded or missing is recorded in `unresolved`, never fabricated.
    Files of an assignment without a static header are `unlabeled`, never negatives
    (see `LABEL_RULE`).
    """
    files = list(files)
    by_key: Dict[Tuple[str, str], List[HumanFile]] = {}
    for f in files:
        by_key.setdefault((f.assignment, f.student), []).append(f)

    clusters: Dict[str, Cluster] = {}
    cluster_of: Dict[str, str] = {}
    student_clusters: Dict[str, List[str]] = {}
    unresolved: List[Dict[str, str]] = []
    merged_lines = 0

    for assignment in sorted(gt):
        lines = gt[assignment]
        uf = UnionFind()
        for line in lines:
            ordered = sorted(line)
            for student in ordered[1:]:
                uf.union(ordered[0], student)
            uf.add(ordered[0])
        components = uf.groups()  # root (smallest student) -> sorted students
        merged_lines += len(lines) - len(components)

        for number, root in enumerate(sorted(components), start=1):
            cluster_id = f"{assignment}#{number:02d}"
            members: List[str] = []
            missing: List[str] = []
            for student in components[root]:
                student_clusters.setdefault(student, []).append(cluster_id)
                present = by_key.get((assignment, student), [])
                live = sorted(f.id for f in present if not f.excluded)
                if live:
                    members.extend(live)
                    continue
                missing.append(student)
                unresolved.append(
                    {
                        "cluster": cluster_id,
                        "assignment": assignment,
                        "student": student,
                        "reason": "excluded" if present else "no_file",
                    }
                )
            for sample_id in members:
                cluster_of[sample_id] = cluster_id
            if members:
                clusters[cluster_id] = Cluster(
                    cluster_id, assignment, tuple(components[root]), tuple(members), tuple(missing)
                )

    ambiguous: Dict[str, Set[str]] = {}
    for assignment, lines in (ambiguous_gt or {}).items():
        listed = set().union(*lines) if lines else set()
        static = set().union(*gt.get(assignment, []))
        ambiguous[assignment] = listed - static

    labeled_courses = {_course(a) for a in gt}
    gt_status: Dict[str, str] = {}
    assignment_of: Dict[str, str] = {}
    student_of: Dict[str, str] = {}
    unlabeled: Set[str] = set()
    unheaded: Set[str] = set()
    for f in sorted(files, key=lambda f: f.id):
        if f.excluded:
            continue
        assignment_of[f.id] = f.assignment
        student_of[f.id] = f.student
        if _course(f.assignment) not in labeled_courses:
            gt_status[f.id] = "unlabeled"
            unlabeled.add(_course(f.assignment))
        elif f.id in cluster_of:
            gt_status[f.id] = "positive"
        elif f.student in ambiguous.get(f.assignment, ()):
            gt_status[f.id] = "ambiguous"
        elif f.assignment not in gt:
            gt_status[f.id] = "unlabeled"
            unheaded.add(f.assignment)
        else:
            gt_status[f.id] = "negative"

    return Resolution(
        clusters=clusters,
        cluster_of=cluster_of,
        gt_status=gt_status,
        assignment_of=assignment_of,
        student_of=student_of,
        student_clusters=student_clusters,
        unresolved=unresolved,
        merged_lines=merged_lines,
        unlabeled_courses=sorted(unlabeled),
        unlabeled_assignments=sorted(unheaded),
    )


def pairs(
    resolution: Resolution,
    include_ambiguous: bool = False,
    ids: Optional[Iterable[str]] = None,
) -> Iterator[Tuple[str, str, int]]:
    """Yield (a, b, label) for same-assignment pairs of labelled files, label 1 = same cluster.

    Pairs are emitted per assignment in sorted order with a < b. Unlabeled files never appear,
    ambiguous ones only with `include_ambiguous`, and two files of one student never pair.
    `ids` restricts the pool (e.g. to one split).
    """
    allowed = {"positive", "negative"} | ({"ambiguous"} if include_ambiguous else set())
    keep = set(ids) if ids is not None else None
    pools: Dict[str, List[str]] = {}
    for sample_id, status in resolution.gt_status.items():
        if status in allowed and (keep is None or sample_id in keep):
            pools.setdefault(resolution.assignment_of[sample_id], []).append(sample_id)

    for assignment in sorted(pools):
        pool = sorted(pools[assignment])
        for i, a in enumerate(pool):
            cluster_a = resolution.cluster_of.get(a)
            for b in pool[i + 1 :]:
                if resolution.student_of[a] == resolution.student_of[b]:
                    continue
                yield a, b, int(cluster_a is not None and cluster_a == resolution.cluster_of.get(b))
