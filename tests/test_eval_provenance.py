"""Provenance helpers: the shared atomic writer used by manifests and calibration files."""

import os

import pytest

from models.evaluation import provenance as P


def test_atomic_write_bytes_creates_parents_and_writes_exact_bytes(tmp_path):
    path = tmp_path / "a" / "b" / "out.json"
    assert P.atomic_write_bytes(path, b"one\ntwo\n") == path
    assert path.read_bytes() == b"one\ntwo\n"
    assert [p.name for p in path.parent.iterdir()] == ["out.json"]


@pytest.mark.parametrize("error", [OSError("disk full"), KeyboardInterrupt()])
def test_atomic_write_bytes_failure_keeps_previous_file_and_no_temp(tmp_path, monkeypatch, error):
    path = tmp_path / "out.json"
    path.write_bytes(b"previous\n")

    def failing_replace(src, dst):
        assert os.path.exists(src)  # the temp file was written before the move
        raise error

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(type(error)):
        P.atomic_write_bytes(path, b"new contents\n")
    monkeypatch.undo()
    assert path.read_bytes() == b"previous\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]
