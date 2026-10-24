"""The production image has no scipy: the adapter path (via `baselines`) must not import it eagerly."""

import ast
from pathlib import Path

BASELINES = Path(__file__).resolve().parents[1] / "models" / "graphcodebert" / "v2" / "baselines.py"


def test_baselines_has_no_module_level_scipy_import():
    tree = ast.parse(BASELINES.read_text(encoding="utf-8"))
    eager = [
        node.lineno
        for node in tree.body
        if (isinstance(node, ast.Import) and any(a.name.split(".")[0] == "scipy" for a in node.names))
        or (isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "scipy")
    ]
    assert not eager, f"module-level scipy import at line(s) {eager}"
