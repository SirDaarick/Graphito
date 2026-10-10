# Archive Report: eval-foundation

**Archived**: 2026-10-10
**Verdict at archive**: PASS WITH WARNINGS (see `verify-report.md`; 55/58 requirements compliant, 3 documented deviations, 0 critical)

## Main spec

- `sdd/specs/eval-foundation.md`: final spec (with amendments DS3.3, DS3.4, DS4.1, EM1.6, ER1.7, split unit `letter/Zx/Zy` with years merged, gzip manifest), now the source of truth.

## Archived artifacts

`sdd/archive/2026-10-10-eval-foundation/`: `proposal.md`, `spec.md`, `design.md`, `tasks.md`, `verify-report.md`, `archive-report.md`.

## Engram traceability

| Artifact | Topic key | Observation ID |
|---|---|---|
| Roadmap / audit | `roadmap/model-quality-phase1` | 107 |
| Explore | `sdd/eval-foundation/explore` | 108 |
| Proposal | `sdd/eval-foundation/proposal` | 109 |
| Spec | `sdd/eval-foundation/spec` | 110 |
| Design | `sdd/eval-foundation/design` | 111 |
| Tasks | `sdd/eval-foundation/tasks` | 112 |
| Apply progress | `sdd/eval-foundation/apply-progress` | 113 |
| Real-data findings | `sdd/eval-foundation/real-data-findings` | 115 |
| Session summary | (session) | 116 |

## Delivered

- `models/evaluation/` (seed, normalize, dedup, ground_truth, splits, manifest, metrics, calibration, provenance, report), `scripts/build_split.py`.
- `data/splits/split_v1.json.gz` (manifest sha256 `e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f`, seed 42, byte-identical rebuild).
- Golden set rebuilt from the split (`manifest.json`, `manifest_val.json`, `manifest_none.json`, `manifest_strip-comments.json`); `scripts/benchmark_suite.py` with `calibrated-fit-in-run`, `calibrated-frozen` and `uncalibrated` modes.
- Branch chain (not pushed): `feat/eval-foundation` <- `-01-core` <- `-02-split` <- `-03-metrics` <- `-04-benchmark` <- `-05-data`.

## Carried forward

- Deferred review follow-ups: `tasks.md`, WU11 section.
- Thesis caveats: GT negatives are noisy at high similarity (364,125 of 365,329 near-dup negative pairs are identical after normalization); 1,121 students appear in more than one split; sibling assignments of a topic can land in different splits.
- Next change: SDD-2 `fix-charcnn-implementation` (consumes `load_split`; include a load-and-infer smoke test for `models/char_cnn/best_model.pth`).
