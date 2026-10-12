# Verify report: backend-model-integration (SDD-4)

**Verdict: PASS WITH FINDINGS** (0 CRITICAL, 3 WARNING, 2 SUGGESTION). Verified at `bfdfcd3` on `feat/bmi-05-figures`.

## Evidence base

- Full suite: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider` -> 1307 passed, 1 skipped, 0 failed.
- Frontend: `npm run lint`, `npm run typecheck`, `npx vitest run` (58 passed), `npm run build` -> all exit 0.
- Docker E2E in REAL mode (local compose Postgres 16 + Chroma): `/health` ready with per-channel keys and shas; migrations applied twice (exit 0); reindex dry run then `--apply` twice (`indexed=2 failures=0`); single vs batch parity on every AS1.2 field; tampered artifact -> `inference_ready=false` (`sha_mismatch`), 503 on single and batch, row counts unchanged. Details in `tasks.md` (closing evidence).
- Static greps of source for the requirements below.

## Coverage

| Group | Status | Evidence |
|---|---|---|
| DA1-DA3 deploy artifacts, settings, loader | Covered | `models/deploy/` tracked; `backend/tests/test_deploy_artifacts.py`, `test_artifacts_loader.py` (sha mismatch, schema, key mismatch, null threshold, numpy-only load) |
| AS1-AS3 shared scoring, Channel A/B | Covered | `ScoringService` used by single, async and batch; parity in tests and Docker E2E; abstention -> null score, `ABSTENIDO` |
| AS4 decision matrix | Covered | `backend/tests/test_scoring_domain.py` (table-driven) |
| AS5-AS7 thresholds, fail-closed, stub label | Covered | stub built only in the STUB branch of `build_runtime` (`runtime.py`); unknown mode not ready; tamper E2E |
| AS8-AS9 GCB secondary, non-blocking inference | Covered | GCB never feeds `decide()` |
| AR1-AR4 API, frontend, PDF, XAI | Covered | `test_reporting.py`, `test_frontend_contract.py`, vitest |
| RI1-RI3 reference indexing | Covered | `test_reference_creation.py`, `test_reindex_chroma.py`; Docker reindex |
| CI8.1, BF1 fusion | Covered | no `backend/app` module imports `models.fusion` |
| MG1 migration | Covered | applied twice on Postgres 16; `bd0e18d` adds the canonical verdict labels to a legacy `dictamenenum` |
| SC1 figures from run metrics | Covered | `tests/test_generate_tt_figures.py` |
| NF1-NF5 | Covered | |

## Findings

- **W1 (WARNING, resolved):** tasks 2.1 and 2.5 were unchecked although the bundle was built and committed (`dc60d0e`). Marked with evidence.
- **W2 (WARNING, open, user-owned):** `.env.example` does not document `INFERENCE_MODE`, `ALLOW_UNCALIBRATED`, `GCB_SECONDARY_ENABLED`, `APP_ENV`, `INFERENCE_WORKERS` (task 4.4). The file is blocked by the session's permission settings.
- **W3 (WARNING, open):** legacy dead code kept for one root test: `backend/app/infrastructure/inference/stub_engine.py` `compute_decision` (emits `CONFORMIDAD_BASE`) and deprecated `THRESHOLD_SEM/AI` in `backend/app/config.py`. Nothing in the decision path calls them; remove them together with `tests/test_calibration_experiment.py`.
- **S1 (SUGGESTION, pre-existing):** the batch worker marks `COMPLETADO` and logs success even when every file errored.
- **S2 (SUGGESTION):** `Documentacion/Documento/capitulos/modelado.tex` still references removed figures and the old model description.

## Next

No CRITICAL findings block archive.
