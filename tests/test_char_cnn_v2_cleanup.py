"""Deprecations and the legacy trainer delegation (CT10, D1)."""

import ast
import importlib
import inspect
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parent.parent
LEGACY_HELPERS = ("evaluate", "compute_metrics", "train_epoch")
REMOVED_WRITERS = ("save_checkpoint", "setup_model", "run_training")


class TestDeprecations:
    def test_poc_trainer_is_removed(self):
        assert not (ROOT / "data" / "train_charcnn.py").exists()

    def test_deprecated_dataset_files_remain_and_are_marked(self):
        module = ROOT / "models" / "char_cnn" / "prepare_dataset.py"
        assert module.is_file() and (ROOT / "models" / "char_cnn" / "dataset_manifest.json").is_file()
        doc = ast.get_docstring(ast.parse(module.read_text(encoding="utf-8")))
        assert "Deprecated" in doc and "split_v1" in doc

    def test_importing_prepare_dataset_warns(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "models.char_cnn.prepare_dataset", raising=False)
        with pytest.warns(DeprecationWarning, match="split_v1"):
            importlib.import_module("models.char_cnn.prepare_dataset")


class TestLegacyTrainer:
    def test_keeps_the_imported_helpers_and_drops_the_checkpoint_writers(self):
        legacy = importlib.import_module("models.char_cnn.train")
        for name in LEGACY_HELPERS:
            assert callable(getattr(legacy, name)), name
        for name in REMOVED_WRITERS:
            assert not hasattr(legacy, name), name
        assert "best_model" not in inspect.getsource(legacy)

    def test_main_delegates_to_the_v2_trainer(self, monkeypatch):
        from models.char_cnn.v2 import train as v2_train

        calls = []
        monkeypatch.setattr(v2_train, "main", lambda argv=None: calls.append(argv) or 7)
        legacy = importlib.import_module("models.char_cnn.train")
        assert legacy.main(["--epochs", "1"]) == 7
        assert calls == [["--epochs", "1"]]

    def test_figure_script_imports_still_resolve(self):
        legacy = importlib.import_module("models.char_cnn.train")
        tree = ast.parse((ROOT / "scripts" / "generate_tt_figures.py").read_text(encoding="utf-8"))
        names = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "models.char_cnn.train"
            for alias in node.names
        ]
        # SDD-4 task 11.2: the figures script reads runs/*/metrics.json and must not import the
        # legacy trainer; the legacy names stay importable for other consumers.
        assert names == []
        assert all(hasattr(legacy, n) for n in ("evaluate", "compute_metrics", "train_epoch"))
