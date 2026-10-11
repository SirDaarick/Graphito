# Archive Report: fix-charcnn-implementation

**Archived**: 2026-10-11
**Verdict at archive**: PASS WITH WARNINGS (see `verify-report.md`; 54/56 requirements compliant, 2 documented deviations stricter than the spec (CP10.2 mixed version pairs raise; CT9.2 promote guards), 0 critical)

## Main spec

- `sdd/specs/fix-charcnn-implementation.md`: final spec with orchestrator reconciliations (CP5.2 whole print-line removal, CP6.1 line-preserving whitespace, CI3.1 evenly spaced windows), now the source of truth for the CharCNN v2 channel.

## Archived artifacts

`sdd/archive/2026-10-11-fix-charcnn-implementation/`: `proposal.md`, `spec.md`, `design.md`, `tasks.md`, `verify-report.md`, `archive-report.md`.

## Engram traceability

| Artifact | Topic key | Observation ID |
|---|---|---|
| Explore | `sdd/fix-charcnn-implementation/explore` | 118 |
| Proposal | `sdd/fix-charcnn-implementation/proposal` | 119 |
| Spec + design | `sdd/fix-charcnn-implementation/spec-design` | 120 |
| Tasks | `sdd/fix-charcnn-implementation/tasks` | 121 |
| Apply progress | `sdd/fix-charcnn-implementation/apply-progress` | 207 |

## Delivered

- `models/char_cnn/v2/`: symmetric preprocessing v2 with leak guard, padding-invariant model (masked pooling, channel LayerNorm), windowed scoring, manifest-backed data and 1:1 epoch sampler, seeded trainer with val-AUC selection, val-only calibration and single test evaluation, shortcut audit, legacy baseline, fail-safe promote and re-evaluation CLIs, shared run/exit-code contract (`runs.py`).
- `models/char_cnn/inference.py`: version-dispatching facade; legacy checkpoints keep the frozen path (golden within 1e-6); new keys `score`, `abstained`, `n_windows`, `preproc_version`, `arch_version`.
- Real runs (reports committed, no weights): `runs/char_cnn/20261011-015734/` (v2: test representatives ROC-AUC 0.994 [0.991, 0.996], PR-AUC 0.958; 1% FPR target holds, 5% does not on the all-files view) and `runs/char_cnn_legacy/20261011-033124/` (contaminated, not comparable).
- Branch chain (not pushed): `feat/fix-charcnn-implementation` <- `-01-v2core` <- `-02-facade` <- `-03-trainer` <- `-04-baseline` <- `-05-run`.
- `models/char_cnn/best_model.pth` (user's uncommitted version, sha256 `d3692747…`) untouched; nothing promoted.

## Carried forward

- Deferred review follow-ups: `tasks.md` (WU7/WU8 sections).
- Thesis caveats: residual course-convention shortcuts (`std::`, `using namespace`, length); 99% of AI test files from two generators; results are in-distribution only.
- Suggested before SDD-4: an abstention-filtered all-files view (1,333 of 9,318 human files are below the abstention length but scored), threshold re-validation on the deployment population, and the decision to promote and recalibrate `THRESHOLD_AI`.
- Next change: SDD-3 `fix-graphcodebert-dfg-input`.
