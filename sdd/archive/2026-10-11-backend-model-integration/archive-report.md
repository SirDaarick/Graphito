# Archive Report: backend-model-integration

**Archived**: 2026-10-11
**Verdict at archive**: PASS WITH FINDINGS (see `verify-report.md`; 0 critical; 3 warnings, 2 suggestions; W1 resolved; W2, W3, S1, S2 open and user-owned)
**Verified at**: `bfdfcd3` on `feat/bmi-05-figures`

## Main spec

- `sdd/specs/backend-model-integration.md`: final spec (published copy of `spec.md` in this archive). The reconciled decisions (AS5.2 client thresholds ignored in all modes, AS8.2 GCB startup failure blocks readiness unless `GCB_SECONDARY_ENABLED=false`, MG1.1 real column names) are already in the spec text.

## Archived artifacts

`sdd/archive/2026-10-11-backend-model-integration/`: `proposal.md`, `spec.md`, `design.md`, `tasks.md`, `verify-report.md`, `archive-report.md`.

## Engram traceability

No Engram memory tool was available in this session, so no observation IDs were recorded. The artifacts are file-backed; their expected topic keys are listed for later mirroring:

| Artifact | Topic key |
|---|---|
| Proposal | `sdd/backend-model-integration/proposal` |
| Spec | `sdd/backend-model-integration/spec` |
| Design | `sdd/backend-model-integration/design` |
| Tasks | `sdd/backend-model-integration/tasks` |
| Verify report | `sdd/backend-model-integration/verify-report` |
| Archive report | `sdd/backend-model-integration/archive-report` (not saved to Engram) |

## Delivered

- Deploy artifacts in `models/deploy/` (manifest `graphito.deploy-manifest/v1`; Jaccard isotonic `fpr_0.05` threshold 0.000588; CharCNN `fpr_0.01` threshold 0.1715), with the `.gitignore` exception for `channel_b/best.pth` (commits `dc60d0e`, `0c0c22d`).
- Scoring domain (20-cell decision matrix), settings, artifact loader, fail-closed REAL runtime and 503 gate.
- Fingerprinted Chroma collection, embed-before-commit reference creation, `scripts/reindex_references.py`.
- Stop-on-error migrations; enum fix `bd0e18d`.
- Shared `ScoringService` for single, async and batch analysis.
- Additive API fields, honest PDF, flag-driven XAI, frontend without thresholds or invented values.
- Figures from `runs/*/metrics.json`; `models/fusion.py` marked research-only.
- Closing evidence: Docker REAL E2E (parity, tamper gives 503 with no row changes); pytest 1307 passed, 1 skipped; frontend lint, typecheck, vitest (58) and build pass.

## Known follow-ups (open, user-owned; do not block archive)

- **W2**: `.env.example` does not document `INFERENCE_MODE`, `ALLOW_UNCALIBRATED`, `GCB_SECONDARY_ENABLED`, `APP_ENV`, `INFERENCE_WORKERS` (task 4.4). Blocked by session permissions.
- **W3**: legacy `compute_decision` in `backend/app/infrastructure/inference/stub_engine.py` (emits `CONFORMIDAD_BASE`) and deprecated `THRESHOLD_SEM/AI` in `backend/app/config.py`. Remove together with `tests/test_calibration_experiment.py`.
- **S1**: the batch worker sets `COMPLETADO` and logs success even when every file errored (pre-existing).
- **S2**: `Documentacion/Documento/capitulos/modelado.tex` still references removed figures and the old model description.

## Git

Not committed. Source folder `sdd/backend-model-integration/` is to be removed by the user after the archive copy is verified.
