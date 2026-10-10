"""Numpy MinHash/LSH dedup: exact Jaccard, estimate accuracy, LSH recall, overflow safety."""

import numpy as np
import pytest

from models.evaluation.dedup import (
    MERSENNE_PRIME,
    UnionFind,
    estimate_jaccard,
    jaccard,
    lsh_candidates,
    make_permutations,
    minhash,
    shingle_hashes,
    token_ids,
)


def _doc(tag: str, n: int = 400) -> list:
    """A token stream whose tokens are unique to `tag` (distinct docs share no shingle)."""
    return [f"{tag}_{i}" for i in range(n)]


def _mutate(tokens: list, step: int) -> list:
    """Replace every `step`-th token; with step >= 5 each edit alters exactly 5 shingles."""
    out = list(tokens)
    for p in range(10, len(out), step):
        out[p] = f"edit_{p}"
    return out


def _sig(tokens, a, b):
    return minhash(shingle_hashes(token_ids(tokens)), a, b)


def test_jaccard_is_exact_on_sorted_unique_arrays():
    a = np.array([1, 2, 3, 4], dtype=np.uint32)
    b = np.array([3, 4, 5], dtype=np.uint32)
    assert jaccard(a, b) == pytest.approx(2 / 5)
    assert jaccard(a, a) == 1.0
    assert jaccard(a, np.array([9], dtype=np.uint32)) == 0.0
    assert jaccard(np.empty(0, dtype=np.uint32), np.empty(0, dtype=np.uint32)) == 0.0


def test_token_ids_are_stable_and_below_the_modulus():
    ids = token_ids(["int", "x", "int"])
    assert ids.dtype == np.uint64
    assert ids[0] == ids[2] != ids[1]
    assert (ids < MERSENNE_PRIME).all()
    assert (token_ids(["int", "x", "int"]) == ids).all()


def test_shingle_hashes_are_unique_sorted_uint32():
    ids = token_ids([f"t{i}" for i in range(20)] * 2)
    sh = shingle_hashes(ids, k=5)
    assert sh.dtype == np.uint32
    assert (np.diff(sh.astype(np.int64)) > 0).all()
    assert sh.size == 20  # 40 tokens, period 20 -> 20 distinct 5-grams


def test_shingle_hashes_short_input_and_empty():
    assert shingle_hashes(token_ids(["a", "b", "c"]), k=5).size == 1
    assert shingle_hashes(token_ids([]), k=5).size == 0


def test_shingle_hashes_depend_on_token_order():
    fwd = shingle_hashes(token_ids(list("abcdefgh")))
    rev = shingle_hashes(token_ids(list("hgfedcba")))
    assert jaccard(fwd, rev) == 0.0


def test_modulus_is_mersenne_31():
    assert MERSENNE_PRIME == 2**31 - 1


def test_minhash_has_no_uint64_overflow_at_the_extremes():
    p = MERSENNE_PRIME
    sh = np.array([p - 1, p - 2, 12345, 0], dtype=np.uint32)
    a = np.array([p - 1, p - 2, 1], dtype=np.uint64)
    b = np.array([p - 1, 0, p - 2], dtype=np.uint64)
    expected = [min((int(ai) * int(x) + int(bi)) % p for x in sh) for ai, bi in zip(a, b)]
    assert (p - 1) * (p - 1) + (p - 1) < 2**63  # worst case stays far from uint64 wraparound
    assert minhash(sh, a, b).tolist() == expected


def test_minhash_chunking_matches_the_direct_formula():
    a, b = make_permutations(16, seed=3)
    sh = np.arange(1, 9000, dtype=np.uint32) * np.uint32(7)  # spans several internal chunks
    expected = [min((int(ai) * int(x) + int(bi)) % MERSENNE_PRIME for x in sh) for ai, bi in zip(a, b)]
    assert minhash(sh, a, b).tolist() == expected


def test_permutation_parameters_are_valid_and_seeded():
    a, b = make_permutations(128, seed=1)
    assert a.shape == b.shape == (128,)
    assert (a >= 1).all() and (a < MERSENNE_PRIME).all() and (b < MERSENNE_PRIME).all()
    a2, b2 = make_permutations(128, seed=1)
    a3, _ = make_permutations(128, seed=2)
    assert (a == a2).all() and (b == b2).all()
    assert not (a == a3).all()


def test_minhash_is_deterministic_and_empty_sets_use_the_sentinel():
    a, b = make_permutations()
    doc = _doc("d")
    assert (_sig(doc, a, b) == _sig(doc, a, b)).all()
    empty = minhash(np.empty(0, dtype=np.uint32), a, b)
    assert (empty == MERSENNE_PRIME).all()


def test_minhash_estimate_tracks_exact_jaccard_on_planted_pairs():
    a, b = make_permutations(128, seed=0)
    base = _doc("base")
    errors = []
    for step in (80, 60, 100):  # exact Jaccard roughly 0.8-0.9
        other = _mutate(base, step)
        exact = jaccard(shingle_hashes(token_ids(base)), shingle_hashes(token_ids(other)))
        est = estimate_jaccard(_sig(base, a, b), _sig(other, a, b))
        errors.append(abs(est - exact))
        assert 0.7 < exact < 0.95
    assert max(errors) <= 0.1
    assert estimate_jaccard(_sig(base, a, b), _sig(base, a, b)) == 1.0
    assert estimate_jaccard(_sig(base, a, b), _sig(_doc("other"), a, b)) <= 0.05


def test_lsh_finds_planted_near_duplicates_and_nothing_else():
    a, b = make_permutations(128, seed=0)
    docs, planted = [], set()
    for k in range(30):
        original = _doc(f"p{k}")
        docs.extend([original, _mutate(original, 100)])  # exact Jaccard ~ 0.88
        planted.add((2 * k, 2 * k + 1))
    sigs = np.stack([_sig(d, a, b) for d in docs])

    found = set(lsh_candidates(sigs, bands=16, rows=8))

    assert found <= planted  # unrelated docs share no shingle, hence no band
    assert len(found & planted) / len(planted) >= 0.9


def test_lsh_candidates_are_sorted_pairs_and_validate_shape():
    sig = np.zeros((3, 128), dtype=np.uint64)
    assert lsh_candidates(sig) == [(0, 1), (0, 2), (1, 2)]
    with pytest.raises(ValueError):
        lsh_candidates(np.zeros((2, 64), dtype=np.uint64), bands=16, rows=8)


def test_union_find_groups_with_smallest_member_as_root():
    uf = UnionFind()
    for item in ("c", "a", "b", "z", "y", "lonely"):
        uf.add(item)
    assert uf.union("c", "a") is True
    assert uf.union("a", "b") is True
    assert uf.union("b", "c") is False
    uf.union("z", "y")
    assert uf.connected("a", "c") and not uf.connected("a", "z")
    assert uf.find("c") == "a"
    assert uf.groups() == {"a": ["a", "b", "c"], "lonely": ["lonely"], "y": ["y", "z"]}


def test_union_find_adds_unknown_items_lazily_and_is_order_independent():
    left, right = UnionFind(), UnionFind()
    for x, y in [(1, 2), (3, 4), (2, 3)]:
        left.union(x, y)
    for x, y in [(2, 3), (3, 4), (1, 2)]:
        right.union(x, y)
    assert left.groups() == right.groups() == {1: [1, 2, 3, 4]}
    assert 1 in left and 99 not in left
