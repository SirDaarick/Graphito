"""T1 must not depend on PYTHONHASHSEED (set iteration order)."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CODE = (
    "int calc(int alpha, int beta, int gamma) {\n"
    "  int delta = alpha + beta;\n  int eps = delta * gamma;\n  int zeta = eps - alpha;\n"
    "  int eta = zeta + beta + gamma;\n  return eta + delta;\n}\n"
    "int helper(int p, int q) { int r = p * q; int s = r + p; return s; }\n"
    "int main() {\n  int a = 1; int b = 2; int c = calc(a, b, 3); int d = helper(a, c);\n  return d;\n}\n"
)

SCRIPT = (
    "import sys, hashlib\n"
    f"sys.path.insert(0, {str(ROOT)!r})\n"
    "from models.robustness.transforms import t1_rename_identifiers\n"
    f"r = t1_rename_identifiers({CODE!r}, 'c', p=1.0, seed=1234)\n"
    "sys.stdout.write(r.code)\n"
)


def _run(hashseed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=hashseed)
    out = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True, check=True)
    return out.stdout.decode("utf-8")


def test_t1_identical_across_hash_seeds():
    outs = {s: _run(s) for s in ("0", "1", "2", "3", "12345")}
    assert len(set(outs.values())) == 1, "T1 output depends on PYTHONHASHSEED"
    assert outs["0"] != CODE
