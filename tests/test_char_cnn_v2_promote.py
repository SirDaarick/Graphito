"""Guarded promote CLI (CT9): a fake git runner and temporary targets only.

The real `models/char_cnn/best_model.pth` is never a target here: every call passes `--target`
inside `tmp_path`, and the default target is only checked through the parser.
"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from models.char_cnn.v2 import promote as promote_mod
from models.char_cnn.v2.checkpoint import make_checkpoint
from models.char_cnn.v2.config import CharCNNV2Config
from models.char_cnn.v2.model import CharCNNV2

ROOT = Path(__file__).resolve().parent.parent
REAL_CHECKPOINT = ROOT / "models" / "char_cnn" / "best_model.pth"
TINY = dict(embedding_dim=8, conv_kernel_sizes=(3,), conv_filters=(4,), fc_units=8, window=64, stride=32)
OLD_BYTES = b"previous checkpoint bytes"


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class FakeGit:
    """Records `git` calls; answers `status` with a fixed output and return code.

    `ls_files` / `diff` are the return codes of `git ls-files --error-unmatch` (0 tracked,
    1 untracked) and `git diff --quiet HEAD` (0 identical, 1 different).
    """

    def __init__(self, stdout: str = "", returncode: int = 0, error: Exception = None, ls_files: int = 1,
                 diff: int = 1):
        self.stdout, self.returncode, self.error = stdout, returncode, error
        self.codes = {"ls-files": ls_files, "diff": diff}
        self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((list(args), Path(cwd)))
        if self.error is not None:
            raise self.error
        if args[0] in self.codes:
            return subprocess.CompletedProcess(["git", *args], self.codes[args[0]], "", "")
        return subprocess.CompletedProcess(["git", *args], self.returncode, self.stdout, "fatal: boom")


STATUS_CALL = ["status", "--porcelain", "--ignored", "--", "best_model.pth"]


def _write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def run_dir(tmp_path):
    """A finished v2 run: best.pth, config.json (complete), metrics.json and calibration.json."""
    run = tmp_path / "runs" / "char_cnn" / "20260101-000000"
    run.mkdir(parents=True)
    torch.manual_seed(0)
    model = CharCNNV2(CharCNNV2Config(**TINY))
    torch.save(make_checkpoint(model, run_id="char_cnn/20260101-000000", git_sha="abc123", epoch=3), run / "best.pth")
    _write_json(
        run / "config.json",
        {"run_id": "char_cnn/20260101-000000", "status": "complete", "best_sha256": _sha(run / "best.pth")},
    )
    _write_json(
        run / "metrics.json",
        {"threshold_free": {"roc_auc": {"value": 0.91}, "pr_auc": {"value": 0.42}}, "n": 10},
    )
    _write_json(run / "calibration.json", {"method": "platt"})
    return run


@pytest.fixture
def target(tmp_path):
    path = tmp_path / "deploy" / "best_model.pth"
    path.parent.mkdir()
    path.write_bytes(OLD_BYTES)
    return path


def _main(source: Path, target: Path, git: FakeGit, *flags: str) -> int:
    return promote_mod.main([str(source), "--target", str(target), *flags], git=git)


def _sidecar(target: Path) -> Path:
    return target.with_name("best_model.provenance.json")


class TestRefusals:
    @pytest.mark.parametrize("porcelain", [" M best_model.pth\n", "?? best_model.pth\n", "A  best_model.pth\n"])
    def test_modified_or_untracked_target_is_refused(self, run_dir, target, capsys, porcelain):
        git = FakeGit(stdout=porcelain)
        assert _main(run_dir / "best.pth", target, git) == promote_mod.REFUSED_EXIT != 0
        assert target.read_bytes() == OLD_BYTES
        assert not _sidecar(target).exists()
        assert git.calls == [(STATUS_CALL, target.parent)]
        assert "--force" in capsys.readouterr().err

    @pytest.mark.parametrize("git", [FakeGit(returncode=128), FakeGit(error=FileNotFoundError("git"))])
    def test_git_failure_is_refused(self, run_dir, target, git):
        assert _main(run_dir / "best.pth", target, git) == promote_mod.REFUSED_EXIT
        assert target.read_bytes() == OLD_BYTES and not _sidecar(target).exists()

    def test_unversioned_source_is_refused(self, run_dir, target, capsys):
        legacy = run_dir / "legacy.pth"
        torch.save({"model_state_dict": {"w": torch.zeros(2)}, "config": {"alphabet": "abc"}}, legacy)
        git = FakeGit()
        assert _main(legacy, target, git, "--force") == promote_mod.REFUSED_EXIT
        assert "version" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES and not _sidecar(target).exists()
        assert git.calls == []

    @pytest.mark.parametrize("missing", ["metrics.json", "calibration.json", "config.json"])
    def test_unevaluated_run_is_refused(self, run_dir, target, missing):
        (run_dir / missing).unlink()
        assert _main(run_dir / "best.pth", target, FakeGit(), "--force") == promote_mod.REFUSED_EXIT
        assert target.read_bytes() == OLD_BYTES

    def test_failed_run_is_refused(self, run_dir, target, capsys):
        _write_json(run_dir / "config.json", {"run_id": "x", "status": "failed"})
        assert _main(run_dir / "best.pth", target, FakeGit(), "--force") == promote_mod.REFUSED_EXIT
        assert "status" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES


class TestPromotion:
    def test_force_copies_a_dirty_target_and_records_provenance(self, run_dir, target):
        source = run_dir / "best.pth"
        git = FakeGit(stdout=" M best_model.pth\n")
        assert _main(source, target, git, "--force") == 0
        assert target.read_bytes() == source.read_bytes()
        doc = json.loads(_sidecar(target).read_text(encoding="utf-8"))
        assert doc["schema"] == promote_mod.PROVENANCE_SCHEMA
        assert doc["forced"] is True and doc["git_status"] == " M best_model.pth"
        assert doc["run_id"] == "char_cnn/20260101-000000"
        assert Path(doc["run_dir"]) == run_dir
        assert doc["source_sha256"] == _sha(source) == doc["target_sha256"]
        assert doc["previous_sha256"] == hashlib.sha256(OLD_BYTES).hexdigest()
        assert doc["config_sha256"] == _sha(run_dir / "config.json")
        assert doc["calibration_sha256"] == _sha(run_dir / "calibration.json")
        assert doc["calibration_path"].endswith("calibration.json")
        assert (doc["headline"]["roc_auc"], doc["headline"]["pr_auc"]) == (0.91, 0.42)
        assert (doc["arch_version"], doc["preproc_version"]) == (2, 2)
        assert doc["run_git_sha"] == "abc123" and doc["promoted_at"]

    def test_clean_target_is_copied_without_force(self, run_dir, target):
        assert _main(run_dir / "best.pth", target, FakeGit()) == 0
        assert target.read_bytes() == (run_dir / "best.pth").read_bytes()
        assert json.loads(_sidecar(target).read_text(encoding="utf-8"))["forced"] is False

    def test_new_target_has_no_previous_hash(self, run_dir, tmp_path):
        target = tmp_path / "deploy" / "best_model.pth"
        target.parent.mkdir()
        assert _main(run_dir / "best.pth", target, FakeGit()) == 0
        assert json.loads(_sidecar(target).read_text(encoding="utf-8"))["previous_sha256"] is None

    def test_dry_run_writes_nothing(self, run_dir, target, capsys):
        assert _main(run_dir / "best.pth", target, FakeGit(), "--dry-run") == 0
        assert target.read_bytes() == OLD_BYTES
        assert not _sidecar(target).exists()
        assert "dry run" in capsys.readouterr().out

    def test_dry_run_still_reports_a_refusal(self, run_dir, target):
        assert _main(run_dir / "best.pth", target, FakeGit(stdout=" M x\n"), "--dry-run") == promote_mod.REFUSED_EXIT
        assert target.read_bytes() == OLD_BYTES


class TestDefaults:
    def test_default_target_is_the_deployed_checkpoint(self, run_dir):
        args = promote_mod.build_parser().parse_args([str(run_dir / "best.pth")])
        assert args.target == REAL_CHECKPOINT
        assert args.force is False and args.dry_run is False

    def test_exit_codes_come_from_the_shared_runs_module(self):
        from models.char_cnn.v2 import runs

        assert promote_mod.REFUSED_EXIT is runs.REFUSED_EXIT
        assert promote_mod.PARTIAL_WRITE_EXIT is runs.PARTIAL_WRITE_EXIT == 4


# --- PR4 review follow-ups -----------------------------------------------------------------------


class TestIgnoredTarget:
    def test_ignored_untracked_target_is_refused(self, run_dir, target, capsys):
        git = FakeGit(stdout="!! best_model.pth\n", ls_files=1)
        assert _main(run_dir / "best.pth", target, git) == promote_mod.REFUSED_EXIT
        assert "--force" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES and not _sidecar(target).exists()
        assert [call[0][0] for call in git.calls] == ["status", "ls-files"]

    def test_ignored_tracked_target_that_differs_from_head_is_refused(self, run_dir, target):
        git = FakeGit(stdout="!! best_model.pth\n", ls_files=0, diff=1)
        assert _main(run_dir / "best.pth", target, git) == promote_mod.REFUSED_EXIT
        assert target.read_bytes() == OLD_BYTES
        assert git.calls[-1][0] == ["diff", "--quiet", "HEAD", "--", "best_model.pth"]

    def test_ignored_tracked_target_identical_to_head_is_clean(self, run_dir, target):
        git = FakeGit(stdout="!! best_model.pth\n", ls_files=0, diff=0)
        assert _main(run_dir / "best.pth", target, git) == 0
        assert target.read_bytes() == (run_dir / "best.pth").read_bytes()
        assert json.loads(_sidecar(target).read_text(encoding="utf-8"))["forced"] is False

    def test_force_promotes_an_ignored_target(self, run_dir, target):
        git = FakeGit(stdout="!! best_model.pth\n")
        assert _main(run_dir / "best.pth", target, git, "--force") == 0
        doc = json.loads(_sidecar(target).read_text(encoding="utf-8"))
        assert doc["forced"] is True and doc["git_status"] == "!! best_model.pth"


class TestSourceBinding:
    def test_source_must_be_the_runs_best_checkpoint(self, run_dir, target, capsys):
        other = run_dir / "epoch3.pth"
        other.write_bytes((run_dir / "best.pth").read_bytes())
        assert _main(other, target, FakeGit(), "--force") == promote_mod.REFUSED_EXIT
        assert "best.pth" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES and not _sidecar(target).exists()

    def test_run_without_a_recorded_checkpoint_hash_is_refused(self, run_dir, target, capsys):
        _write_json(run_dir / "config.json", {"run_id": "x", "status": "complete"})
        assert _main(run_dir / "best.pth", target, FakeGit(), "--force") == promote_mod.REFUSED_EXIT
        assert "best_sha256" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES

    def test_checkpoint_that_differs_from_the_recorded_hash_is_refused(self, run_dir, target, capsys):
        _write_json(run_dir / "config.json", {"run_id": "x", "status": "complete", "best_sha256": "0" * 64})
        assert _main(run_dir / "best.pth", target, FakeGit(), "--force") == promote_mod.REFUSED_EXIT
        assert "best_sha256" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES


class TestFailSafeWrite:
    def test_source_changed_after_planning_writes_nothing(self, run_dir, target, monkeypatch, capsys):
        source = run_dir / "best.pth"
        original = promote_mod.plan_promotion

        def plan_then_tamper(*args, **kwargs):
            plan = original(*args, **kwargs)
            source.write_bytes(b"tampered after the checks")
            return plan

        monkeypatch.setattr(promote_mod, "plan_promotion", plan_then_tamper)
        assert _main(source, target, FakeGit()) == promote_mod.REFUSED_EXIT
        assert "changed" in capsys.readouterr().err
        assert target.read_bytes() == OLD_BYTES
        assert sorted(p.name for p in target.parent.iterdir()) == ["best_model.pth"]

    def test_sidecar_failure_restores_the_target_and_the_previous_sidecar(
        self, run_dir, target, monkeypatch, capsys
    ):
        old_sidecar = b'{"previous": "promotion"}\n'
        _sidecar(target).write_bytes(old_sidecar)

        def disk_full(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(promote_mod, "_commit_sidecar", disk_full)
        assert _main(run_dir / "best.pth", target, FakeGit()) == promote_mod.PARTIAL_WRITE_EXIT == 4
        err = capsys.readouterr().err
        assert err.startswith("ERROR:") and "disk full" in err and "restored" in err
        assert target.read_bytes() == OLD_BYTES
        assert _sidecar(target).read_bytes() == old_sidecar
        assert sorted(p.name for p in target.parent.iterdir()) == ["best_model.provenance.json", "best_model.pth"]

    def test_sidecar_failure_on_a_new_target_removes_it(self, run_dir, tmp_path, monkeypatch):
        target = tmp_path / "deploy" / "best_model.pth"
        target.parent.mkdir()

        def disk_full(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(promote_mod, "_commit_sidecar", disk_full)
        assert _main(run_dir / "best.pth", target, FakeGit()) == promote_mod.PARTIAL_WRITE_EXIT
        assert list(target.parent.iterdir()) == []
