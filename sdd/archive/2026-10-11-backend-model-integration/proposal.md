# Proposal: Backend Model Integration (backend-model-integration)

## Intent

SDD-1..3 produced honest, calibrated models (CharCNN v2, GraphCodeBERT v2 zero-shot, Jaccard baseline) but the backend still scores with the old path. The exploration found the verdict a teacher sees is not trustworthy:
- **Two scorings.** Single analysis maps with a sigmoid (`analysis_orchestrator.py:47-76,:140,:338`), batch with a linear map (`batch_analysis_service.py:235-240`); batch never persists decision indicators (`:271`). The frontend always sends thresholds 0.85/0.20 (`api.ts:309-322`).
- **Silent fakes.** `real_engine.py:61-84` falls back to the stub in REAL mode, writes fake embeddings to Chroma (`problem_service.py:71-85`), drops CharCNN abstention (prob 0.05 = human) and still passes an adapter path. `chroma_adapter.py:110` turns a missing distance into similarity 1.0; `:121-123` turns errors into `[]` and so `SIN_ALERTAS`. No reference also yields `SIN_ALERTAS`.
- **Uncalibrated decision.** `StubInferenceEngine.compute_decision` decides in REAL mode; `discrepancia_score = sim x prob` is unvalidated; `models/fusion.py` is dead for the backend.
- **Dishonest reporting.** XAI heuristics are labelled as model output; the PDF falls back to `CONFORMIDAD`; `SimilarityReportModal` invents 62/85 and maps unknown verdicts to "Conforme".

This is SDD-4, the last change of Phase 1: wire the validated artifacts in, fail closed, and report only what is measured.

## Scope

### In Scope
- Channel A Jaccard calibration (val only, isotonic, `fpr_0.05`) via existing `models/evaluation` `build_calibration`; first, eval-side task.
- Tracked deploy artifacts directory with a manifest (paths, sha256, source run ids, threshold keys), mounted read-only in compose.
- One scoring service shared by single and batch analysis; decision from calibrated flags only.
- REAL mode fails closed; STUB mode dev-only and labelled.
- Chroma: fingerprinted collection for the GCB v2 secondary signal, reindex script, error-raising adapter.
- Schema migration (nullable scores, provenance columns, new verdict states).
- Honest API, frontend, PDF and XAI output.
- Torch inference off the event loop (if small).
- `scripts/generate_tt_figures.py` reads `runs/*/metrics.json`.

### Out of Scope
- Student-vs-student comparison flow.
- Any retraining, fine-tuning or LoRA work; Phase 2.
- Changing `models/evaluation` APIs (consumed only).
- Overwriting `models/char_cnn/best_model.pth` (user's uncommitted legacy file); running the promote CLI.
- Deleting the legacy Chroma collection or legacy DB rows.

## Capabilities

### New Capabilities
- `deployed-model-artifacts`: deploy directory, manifest with sha256 and threshold keys, Jaccard calibration artifact, settings-driven loading, checksum verification.
- `analysis-scoring`: single scoring service; Channel A = max 5-token-shingle Jaccard over the problem's references (`reference_id` = argmax) with `fpr_0.05`; Channel B = CharCNN v2 with `fpr_0.01` (0.1715); 2x2 gate on calibrated flags; states `NO_EVALUABLE`, `SIN_REFERENCIA`; fail-closed REAL mode; GCB v2 as non-deciding secondary signal.
- `analysis-reporting`: API fields, frontend, PDF and XAI showing method, engine, versions, calibration state, abstention and the "not validated against reference-derived plagiarism" label; no invented values.
- `reference-indexing`: embed-before-commit, fingerprinted Chroma collection, reindex script, strict adapter errors.

### Modified Capabilities
- `charcnn-inference`: CI8.1 (backend uses legacy keys only) changes; the backend consumes `score`/`abstained`.
- `bimodal-fusion`: documented as research-only; not on the runtime decision path.

## Approach

1. **Eval-side artifacts.** Fit the Jaccard calibration on val with `build_calibration`; copy CharCNN v2 `best.pth` + calibration and the Jaccard calibration into the deploy directory; write the manifest.
2. **Loader and settings.** `load_calibration` (numpy only). Settings: `CHARCNN_CHECKPOINT`, `CHARCNN_CALIBRATION`, `CHARCNN_THRESHOLD_KEY=fpr_0.01`, `CHANNEL_A_METHOD=jaccard`, `CHANNEL_A_CALIBRATION`, `CHANNEL_A_THRESHOLD_KEY=fpr_0.05`, `GCB_INPUT_VERSION=v2`. Startup verifies sha256.
3. **Scoring service.** Single and batch call the same function, so the same submission gets the same score. Channel A reads reference code from Postgres, so the decision never depends on Chroma. Abstention or missing calibration yields `NO_EVALUABLE`; no reference yields `SIN_REFERENCIA`. Client thresholds are ignored in REAL mode. `discrepancia_score` becomes nullable and labelled "not validated".
4. **Fail closed.** No stub fallback in REAL; `inference_ready` health; 503 when not ready. An uncalibrated state is only allowed behind `ALLOW_UNCALIBRATED` and is reported as such. STUB results carry `engine=stub`. The adapter path is no longer passed.
5. **Chroma.** New collection keyed by embedding fingerprint (model, `input_version`, pooling); legacy collection untouched; embed before commit; missing distance and adapter errors raise.
6. **Schema.** Nullable score columns (`models.py:161-162`); new columns (`engine`, `estado_canal_a/b`, `flag_a/b`, `umbral_a/b`, `calibracion_sha_a/b`, `checkpoint_sha_b`, `canal_a_metodo`, `gcb_similarity`); `ALTER TYPE` adds `NO_EVALUABLE`/`SIN_REFERENCIA`; legacy rows marked; `apply_migrations.py` stops on error.
7. **Reporting.** Additive API fields. Frontend stops sending thresholds, drops invented fallbacks, renders unknown/`NO_EVALUABLE` as "no evaluable", shows Channel A method and the GCB secondary signal as "exploratory, zero-shot". PDF prints method, calibration state, abstention and the label, and drops discrepancy. XAI rules are relabelled as heuristics, add a file-level similarity row and follow the decision flags.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `models/evaluation/` (CLI use only), deploy artifacts dir (name in design), `docker-compose.yml` | New/Modified | Jaccard calibration, manifest, read-only mount |
| `backend/app/config.py` | Modified | Artifact and threshold-key settings |
| `backend/app/application/orchestrator/analysis_orchestrator.py`, `services/batch_analysis_service.py` | Modified | Delegate to the shared scoring service |
| `backend/app/application/services/` | New | Scoring service, artifact loader |
| `backend/app/infrastructure/inference/real_engine.py`, `stub_engine` | Modified | Fail closed, abstention, no adapter, engine label |
| `backend/app/infrastructure/vector_store/chroma_adapter.py`, `problem_service.py`, reindex script | Modified/New | Fingerprinted collection, strict errors, embed before commit |
| `backend/app/infrastructure/database/models.py`, `migrations/migration_features.sql`, `apply_migrations.py` | Modified | Nullable scores, provenance columns, enum values, stop on error |
| `backend/app/presentation/` (schemas, endpoints), `xai_service.py`, PDF generator | Modified | Additive fields, honest labels |
| `frontend/src/lib/api.ts`, `components/` (`SimilarityReportModal`, `EvidenceDrawer`, xai) | Modified | No thresholds, no invented values, new states |
| `models/fusion.py` | Modified (docs) | Research-only note |
| `scripts/generate_tt_figures.py` | Modified | Read metrics from `runs/` |
| `backend/tests/` (`conftest.py`), `tests/` | Modified/New | Fake artifacts, non-constant vector store, parity and fail-closed tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Calibrations (student-vs-student, Bosnian corpus) may not transfer to reference comparison | High | "Not validated" label on every reference-based score; teacher decides |
| Domain shift to ESCOM submissions | High | Same label; thresholds and sha256 shown on reports |
| CharCNN shortcuts (formatting, comments) | Med | Shown as one signal, abstention honoured, no fusion score |
| Existing DB rows lack provenance | High | Columns nullable; rows marked legacy; never rescored silently |
| PG enum `ALTER TYPE` not transactional on older PG / migration errors swallowed | Med | Separate idempotent statements; `apply_migrations.py` stops on error |
| Chroma reindex cost and drift | Med | New collection, legacy untouched; GCB never decides |
| Frontend has no test runner | High | `npm run lint` + `npm run build`; backend contract tests cover fields |
| Work exceeds the 400-line review budget | High | Chained PR slices planned in tasks |

## Rollback Plan

Work lands as work-unit commits on `feat/backend-model-integration`; revert them. Setting `INFERENCE_MODE=STUB` restores a running system without artifacts. Migrations are additive (nullable columns, new enum values, new collection); old code ignores them, and the legacy Chroma collection and `models/char_cnn/best_model.pth` are never modified.

## Dependencies

- SDD-1 `eval-foundation` (`build_calibration`, `load_calibration`, Jaccard/normalize helpers, `split_v1`).
- SDD-2 CharCNN v2 run (`best.pth`, calibration with `fpr_0.01`); SDD-3 GCB v2 (`input_version="v2"`, mean pooling).
- No new runtime dependencies (calibration needs numpy only).

## Success Criteria

- [ ] Jaccard calibration fitted on val only; manifest sha256 match the deployed files.
- [ ] The same submission gets identical scores and verdict through single and batch paths.
- [ ] REAL mode with missing/invalid artifacts returns 503 and writes nothing to Chroma or Postgres.
- [ ] CharCNN abstention and missing calibration produce `NO_EVALUABLE`; no reference produces `SIN_REFERENCIA`; a missing Chroma distance raises.
- [ ] Client thresholds have no effect in REAL mode; thresholds come from the configured keys.
- [ ] Reports (API, UI, PDF, XAI) show method, engine, calibration state and the "not validated" label, and contain no invented values.
- [ ] `pytest tests/ backend/tests/` passes; `npm run lint` and `npm run build` pass.

## Open Questions

- Should `ALLOW_UNCALIBRATED` be available in the production compose profile, or only in development? Assumed: development only.
