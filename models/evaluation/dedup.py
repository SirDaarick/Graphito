"""Near-duplicate detection in pure numpy: token shingles, MinHash, banded LSH and union-find.

All modular arithmetic uses the Mersenne prime p = 2^31 - 1 on uint64 with every operand
reduced mod p, so `a * x + b < 2^62` and nothing can overflow. (A 2^61 - 1 modulus would
overflow uint64 on `a * x`.) LSH only proposes candidates; callers verify them with the
exact `jaccard` on the shingle sets.
"""

import hashlib
from typing import Dict, Hashable, Iterable, List, Sequence, Set, Tuple

import numpy as np

MERSENNE_PRIME = (1 << 31) - 1
SHINGLE_K = 5
NUM_PERM = 128
LSH_BANDS = 16
LSH_ROWS = 8

_SHINGLE_BASE = 1_000_003
_CHUNK = 4096  # shingles per MinHash block; bounds the (num_perm x chunk) temporary


def token_ids(tokens: Sequence[str]) -> np.ndarray:
    """Map tokens to stable uint64 ids (blake2b-8 reduced mod p), hashing each unique token once."""
    cache: Dict[str, int] = {}
    out = np.empty(len(tokens), dtype=np.uint64)
    for i, token in enumerate(tokens):
        value = cache.get(token)
        if value is None:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big") % MERSENNE_PRIME
            cache[token] = value
        out[i] = value
    return out


def shingle_hashes(ids: np.ndarray, k: int = SHINGLE_K) -> np.ndarray:
    """Sorted unique uint32 hashes of every k-token window (rolling polynomial hash mod p).

    A stream shorter than k yields a single shingle covering the whole stream.
    """
    ids = np.asarray(ids, dtype=np.uint64)
    n = ids.size
    if n == 0:
        return np.empty(0, dtype=np.uint32)
    k = min(k, n)
    windows = n - k + 1
    p = np.uint64(MERSENNE_PRIME)
    base = np.uint64(_SHINGLE_BASE)
    h = np.zeros(windows, dtype=np.uint64)
    for j in range(k):
        h = (h * base + ids[j : j + windows]) % p
    return np.unique(h).astype(np.uint32)


def make_permutations(num_perm: int = NUM_PERM, seed: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Draw MinHash parameters a in [1, p) and b in [0, p) from a local generator."""
    rng = np.random.default_rng(seed)
    a = rng.integers(1, MERSENNE_PRIME, size=num_perm, dtype=np.uint64)
    b = rng.integers(0, MERSENNE_PRIME, size=num_perm, dtype=np.uint64)
    return a, b


def minhash(sh: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """MinHash signature: min over shingles of (a * x + b) mod p, one value per permutation.

    An empty shingle set maps to the sentinel p (no real hash can equal it).
    """
    a = np.asarray(a, dtype=np.uint64)
    b = np.asarray(b, dtype=np.uint64)
    p = np.uint64(MERSENNE_PRIME)
    signature = np.full(a.size, MERSENNE_PRIME, dtype=np.uint64)
    x = np.asarray(sh, dtype=np.uint64) % p
    for start in range(0, x.size, _CHUNK):
        block = x[start : start + _CHUNK]
        values = (a[:, None] * block[None, :] + b[:, None]) % p
        np.minimum(signature, values.min(axis=1), out=signature)
    return signature


def estimate_jaccard(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    """Fraction of equal signature slots, an unbiased estimator of the Jaccard similarity."""
    return float(np.mean(sig_a == sig_b))


def lsh_candidates(
    sigs: np.ndarray, bands: int = LSH_BANDS, rows: int = LSH_ROWS
) -> List[Tuple[int, int]]:
    """Return sorted (i, j), i < j, whose signatures agree on all rows of at least one band."""
    sigs = np.asarray(sigs)
    if bands * rows > sigs.shape[1]:
        raise ValueError(f"bands*rows={bands * rows} exceeds signature length {sigs.shape[1]}")
    pairs: Set[Tuple[int, int]] = set()
    for band in range(bands):
        chunk = np.ascontiguousarray(sigs[:, band * rows : (band + 1) * rows])
        buckets: Dict[bytes, List[int]] = {}
        for i in range(chunk.shape[0]):
            buckets.setdefault(chunk[i].tobytes(), []).append(i)
        for members in buckets.values():
            for x in range(len(members)):
                for y in range(x + 1, len(members)):
                    pairs.add((members[x], members[y]))
    return sorted(pairs)


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    """Exact Jaccard similarity of two sorted unique arrays (0.0 when both are empty)."""
    inter = np.intersect1d(a, b, assume_unique=True).size
    union = a.size + b.size - inter
    return inter / union if union else 0.0


class UnionFind:
    """Disjoint sets over hashable, orderable items; the smallest member is always the root."""

    def __init__(self, items: Iterable[Hashable] = ()) -> None:
        self._parent: Dict[Hashable, Hashable] = {}
        for item in items:
            self.add(item)

    def __contains__(self, item: Hashable) -> bool:
        return item in self._parent

    def add(self, item: Hashable) -> None:
        self._parent.setdefault(item, item)

    def find(self, item: Hashable) -> Hashable:
        self.add(item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:  # path compression
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, x: Hashable, y: Hashable) -> bool:
        """Merge the sets of x and y; return False when they were already joined."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        keep, drop = (rx, ry) if rx < ry else (ry, rx)
        self._parent[drop] = keep
        return True

    def connected(self, x: Hashable, y: Hashable) -> bool:
        return self.find(x) == self.find(y)

    def groups(self) -> Dict[Hashable, List[Hashable]]:
        """Map each root to its sorted members, ordered by root."""
        out: Dict[Hashable, List[Hashable]] = {}
        for item in self._parent:
            out.setdefault(self.find(item), []).append(item)
        return {root: sorted(out[root]) for root in sorted(out)}
