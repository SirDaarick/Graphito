# Tasks: Backend Model Integration (backend-model-integration, SDD-4)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated authored changed lines | ~3,100 (code ~1,400 + tests ~1,300 + docs/frontend ~400); deploy data, lockfiles and run artifacts not counted |
| 400-line budget risk | Medium in total; WU8 and WU10 sit near 400, others 200-350 (advisory only) |
| Chained PRs recommended | Yes |
| Suggested split | PR1 = WU1-2 -> PR2 = WU3-5 -> PR3 = WU6-8 -> PR4 = WU9-10 -> PR5 = WU11 |
| Delivery strategy | ask-on-risk (default; not supplied) |
| Chain strategy | feature-branch-chain (PR1 base = `feat/backend-model-integration`; PR N base = PR N-1 branch) |

Decision needed before apply: Yes (D-A, D-B below; D-A blocks WU2 only, D-B blocks nothing)
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Medium

Push, PR creation and merge stay user decisions. Each WU = one Conventional Commit (English) with tests and docs; ~400 lines is advisory. Behavior tasks are RED (test fails) first, then GREEN. Runner: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider` (baseline 1028 passed, 0 failed); focused: `python -m pytest backend/tests/test_<x>.py -q -p no:cacheprovider`. Frontend: `npm run lint` and `npm run build` in `frontend/`. Backend tests use the `fake_artifacts` fixture (tmp dir, valid `graphito.calibration/v1` isotonic-identity JSON, fake checkpoint bytes, real sha256), the stub engine and an in-memory non-constant vector store. No real weights, Postgres or Chroma in pytest.

Hard constraints for every task: `models/char_cnn/best_model.pth` (user's uncommitted change) is never read, written, stashed-restored by the writer, staged or committed; stage by explicit path, never `git add -A`. No diff under `models/evaluation/` (NF1). No scikit-learn or `peft` in backend requirements (NF3). `INFERENCE_MODE=STUB` must keep running without artifacts (NF5). Legacy Chroma collections and legacy DB rows are never deleted or rescored (NF4). Any task marked **[PARENT]** is run by the orchestrator, not the writer.

Decisions already taken (do not reopen): design D1-D15, the 11 work units and 5 PR slices; spec reconciliation: AS5.2 client thresholds ignored in all modes; AS8.2 GCB startup failure blocks readiness unless `GCB_SECONDARY_ENABLED=false`; MG1.1 uses `backend/migrations/migration_features.sql` with the real column names (`similitud_semantica`, `probabilidad_ia`, `discrepancia_score`, `dictamen`).

### Work Units and Dependencies

| WU | Commit | Depends on | Parallel with |
|----|--------|-----------|---------------|
| 1 | `feat(eval): build_deploy_artifacts script` | none | none (first) |
| 2 | `data(deploy): Jaccard calibration, CharCNN v2, manifest` | 1 | none |
| 3 | `feat(backend): scoring domain, ports, decision matrix` | none (pure code) | WU1-2 (order-independent) |
| 4 | `feat(backend): settings, artifacts loader, readiness, 503` | 2 (for real shape), 3 | none |
| 5 | `feat(backend): fail-closed real engine, thread pool, stub label` | 3, 4 | none |
| 6 | `feat(db): nullable scores, provenance columns, enum values, stop-on-error` | 3 | WU5 (order-independent) |
| 7 | `feat(backend): strict fingerprinted Chroma, embed-before-commit, reindex mode` | 5 | WU6 |
| 8 | `feat(backend): shared ScoringService in single/async/batch` | 4, 5, 6, 7 | none |
| 9 | `feat(backend): API fields, honest PDF, flag-driven XAI` | 8 | none |
| 10 | `feat(frontend): nullable reports, verdict mapping, labels, no thresholds` | 9 (API shape) | none |
| 11 | `docs/chore: fusion note, figures from runs metrics` | 2 | any after WU2 |

Solo-writer rule: single writer; "parallel" means order-independent, not concurrent.

## WU1 - build_deploy_artifacts script (PR1, ~300 lines)

- [ ] 1.1 RED: `tests/test_build_deploy_artifacts.py` with tiny synthetic val pairs (via `tests/eval_factory.py`) and a fake CharCNN run dir: asserts manifest schema `graphito.deploy-manifest/v1`, sha256 of each file, relative non-escaping paths, `fit_set.split == "val"`, `split_manifest_sha256` equals the CharCNN calibration's (DA2.2), refusal (exit 1) when `fpr_0.05` is unachievable (D3), refusal to overwrite differing files without `--force` (D2), atomic write. Spec: DA1.2, DA2.1, DA2.2.
- [ ] 1.2 GREEN: create `scripts/build_deploy_artifacts.py` (consumes `models.evaluation` unchanged: `build_calibration(method="isotonic", targets=(0.05, 0.01))`, `load_calibration`, `validate_calibration`, shingle/Jaccard helpers; score = `dedup.jaccard(shingle_hashes(token_ids(shingle_tokens(code))))` per assignment block; copies CharCNN `best.pth` + `calibration.json`; records `raw_val_threshold_ref`, `achieved_fpr`, `tpr`, git sha/dirty, source runs). Files: `scripts/build_deploy_artifacts.py`, `tests/test_build_deploy_artifacts.py`.
- [ ] 1.3 Document usage in the script docstring and `models/deploy/README.md` (provenance, `--force`, rebuild steps, label "not validated against reference-derived plagiarism").
- [ ] 1.4 Run focused tests, then full suite; commit `feat(eval): build_deploy_artifacts script`.

## WU2 - Deploy artifacts data (PR1, data only)

- [ ] 2.1 **[PARENT]** Decision D-A resolved first (see Decisions). Run `python scripts/build_deploy_artifacts.py --charcnn-run runs/char_cnn/20261011-015734 --gcb-run runs/graphcodebert/20261011-082155` (scores the full val pairs, ~1.6M; may be long, run detached). Verify output: Jaccard `fpr_0.05` threshold non-null, achieved FPR and TPR recorded, CharCNN `fpr_0.01` threshold = 0.1715, manifest sha256s match disk.
- [ ] 2.2 Add `.gitignore` exception `!models/deploy/channel_b/best.pth` (exact path, D1). Confirm `git status` shows `models/deploy/**` and no change to `models/char_cnn/best_model.pth` staging.
- [ ] 2.3 RED/GREEN: `tests/test_deploy_artifacts_integrity.py` reads the committed `models/deploy/` and fails if sha256 differs from the manifest, `fit_set.split != "val"`, key names differ from `fpr_0.05`/`fpr_0.01`, or manifest paths escape the directory (DA1.2, DA2.2). Skip with a clear reason only if the directory is absent.
- [ ] 2.4 Confirm `docker-compose.yml` already mounts `./models:/models:ro` (DA1.3); add a test or comment only if a gap exists (no volume change expected).
- [ ] 2.5 Stage explicit paths; commit `data(deploy): Jaccard calibration, CharCNN v2, manifest`.

## WU3 - Scoring domain, ports, decision matrix (PR2, ~250 lines)

- [ ] 3.1 RED: `backend/tests/test_scoring_domain.py`, table-driven over the design matrix (all 20 A x B combinations incl. positive flag never hidden, SIN_REFERENCIA, VACIO, ABSTENCION, SIN_CALIBRACION); asserts `dictamen` and that `domain/` imports no framework. Spec: AS4.1, AS4.3, AS4.4, AS3.2.
- [ ] 3.2 GREEN: create `backend/app/domain/scoring.py` (`ChannelResult`, `ScoringOutcome`, pure `decide()`), `backend/app/domain/errors.py` (`ArtifactError`, `InferenceError`, `VectorStoreError`, `NotReadyError`), ports `domain/ports/calibration_port.py`, `domain/ports/lexical_similarity_port.py`; reshape `domain/ports/inference_port.py` (`engine`, `embedding_fingerprint`, `readiness()`, `extract_semantic_embedding`, `predict_stylometry`; remove `compute_decision`, `generate_hybrid_embedding`). Update stub/real engines minimally to keep imports valid.
- [ ] 3.3 Reconcile state names: spec AS4.1 names (`EVALUADO`, `NO_CALIBRADO`, `ABSTENIDO`) vs design (`OK`, `SIN_CALIBRACION`, `ABSTENCION`); use the spec strings in persisted/API fields (see Decision D-B) and keep one mapping constant in `scoring.py`.
- [ ] 3.4 Files: `backend/app/domain/{scoring.py,errors.py}`, `backend/app/domain/ports/{inference_port.py,calibration_port.py,lexical_similarity_port.py}`, `backend/tests/test_scoring_domain.py`. Commit `feat(backend): scoring domain, ports, decision matrix`.

## WU4 - Settings, artifacts loader, readiness, 503 (PR2, ~350 lines)

- [ ] 4.1 RED: `backend/tests/test_artifacts_loader.py` using `fake_artifacts`: ok bundle exposes thresholds + all shas (DA3.4); sha mismatch, missing file, unknown schema, missing key, `null` threshold, configured key != manifest key all raise `ArtifactError` with no partial bundle (DA3.2); `ALLOW_UNCALIBRATED=true` with `APP_ENV=production` refused at settings load (D7, DA3.5); isotonic `transform` equals expected values within 1e-9 using numpy only (DA3.3); importing the loader imports neither sklearn nor torch.
- [ ] 4.2 RED: `backend/tests/test_readiness.py`: REAL with corrupted artifact -> `GET /health` shows `inference_ready=false`, `engine`, reason code, no filesystem paths; `POST /analysis/run`, `POST /analysis/batch` and `POST /problems/{id}/references` return 503, rows unchanged, `upsert` never called (AS6.2-6.4).
- [ ] 4.3 GREEN: `backend/app/config.py` (settings from design; delete `THRESHOLD_SEM/AI`; `APP_ENV`, `ALLOW_UNCALIBRATED` validator); `backend/app/infrastructure/models_path.py` (extracted `ensure_on_path()`); `backend/app/infrastructure/artifacts/{__init__,manifest.py,calibration.py,stub_artifacts.py}`; `backend/app/main.py` lifespan builds engine + bundle in a thread, starts degraded; `presentation/api/v1/deps.py` `require_inference_ready`; `/health` fields (D5, D6).
- [ ] 4.4 Update `.env.example` and `docker-compose.yml` backend env for the new settings (production profile must not set `ALLOW_UNCALIBRATED=true`). Update `backend/tests/test_thresholds.py`: settings no longer define thresholds.
- [ ] 4.5 Commit `feat(backend): settings, artifacts loader, readiness, 503`.

## WU5 - Fail-closed real engine, thread pool, stub label (PR2, ~300 lines)

- [ ] 5.1 RED: `backend/tests/test_inference_engines.py`: REAL construction failure raises and no stub instance is created (spy) (AS6.1); `real_engine.py` source contains no stub import and no adapter path (static scan); fake model factories record thread names proving torch never runs on the loop thread (AS9.1, D10); an engine whose `predict` sleeps 0.3 s lets a ticker coroutine advance during two concurrent analyses (AS9); CharCNN `score`/`abstained` consumed, legacy `ai_probability=0.05` never surfaces (CI8.1, AS3); stub carries `engine == "stub"` and abstains below the CharCNN minimum length (AS7.1).
- [ ] 5.2 GREEN: modify `infrastructure/inference/{__init__,real_engine,stub_engine}.py`: no fallback, `ThreadPoolExecutor(max_workers=INFERENCE_WORKERS, thread_name_prefix="inference")` with `run_in_executor`, GCB v2 mean pooling without adapter, embedding fingerprint (sha256 canonical JSON, D12), `readiness()`.
- [ ] 5.3 Commit `feat(backend): fail-closed real engine, thread pool, stub label`.

## WU6 - Schema and migration (PR3, ~200 lines)

- [ ] 6.1 RED: `backend/tests/test_migration.py`: `split_statements()` is pure and keeps `ALTER TYPE ... ADD VALUE IF NOT EXISTS` as separate statements; fake executor failing on statement 3 -> statements 4+ not run, exit code non-zero (MG1.3, D13); static parse: every enum add uses `IF NOT EXISTS`, every `ADD COLUMN` uses `IF NOT EXISTS`, `UPDATE ... SET engine='legacy' WHERE engine IS NULL` present (MG1.1-1.2); `create_all` DB round-trips a report with null scores and `NO_EVALUABLE` (MG1.4).
- [ ] 6.2 GREEN: `backend/app/infrastructure/database/models.py` (nullable `similitud_semantica`, `probabilidad_ia`, `discrepancia_score`, `dictamen`; new columns incl. `puntaje_calibrado_a`, `manifest_sha`, `gcb_estado`; `DictamenEnum` += `NO_EVALUABLE`, `SIN_REFERENCIA`; `estado_*`/`engine` as VARCHAR, D14); `backend/migrations/migration_features.sql` section 8; `backend/apply_migrations.py` (AUTOCOMMIT, one statement per transaction, stop at first error, exit 1).
- [ ] 6.3 Review legacy statements in the SQL file for non-idempotence that stop-on-error would now expose; fix or note in the commit body (design risk).
- [ ] 6.4 **[PARENT, optional]** Apply `python apply_migrations.py` twice against compose Postgres 16 (needs Docker); both runs must exit 0.
- [ ] 6.5 Commit `feat(db): nullable scores, provenance columns, enum values, stop-on-error`.

## WU7 - Strict fingerprinted Chroma, embed-before-commit, reindex (PR3, ~300 lines)

- [ ] 7.1 RED: `backend/tests/test_vector_store.py`: result lacking `distances` raises `VectorStoreError`; failing client raises (not `[]`); empty collection is a valid empty result (RI3); collection name changes when only pooling differs (RI2.1); `stub_{fp[:12]}` for STUB; legacy collection `codigos_referencia*` never touched (RI2.2).
- [ ] 7.2 RED: `backend/tests/test_reference_creation.py`: embedder raises -> 503, no DB row, no upsert; upsert fails -> rollback, no row; DB commit fails after upsert -> `delete_reference` compensation called (RI1). Test double `InMemoryVectorStore` uses real cosine and a `fail` switch (non-constant similarities).
- [ ] 7.3 RED: `backend/tests/test_reindex_chroma.py`: `--mode gcb-v2` reads references from Postgres, upserts into the fingerprinted collection, rerun yields same ids/count, legacy collection count unchanged, non-zero exit on any failure (RI2.3).
- [ ] 7.4 GREEN: `infrastructure/vector_store/{__init__,chroma_adapter}.py`, `domain/ports/vector_store_port.py` (injected collection name, strict errors), `application/services/problem_service.py` (explicit uuid4, embed -> add -> flush -> upsert -> commit), `backend/reindex_chroma.py` (`--mode gcb-v2`), `backend/tests/conftest.py` (fixtures: project root on `sys.path`, `fake_artifacts`, non-constant vector store).
- [ ] 7.5 Commit `feat(backend): strict fingerprinted Chroma, embed-before-commit, reindex mode`.
- [ ] 7.6 **[PARENT, deployment step, not a commit]** After deploy: `python backend/reindex_chroma.py --mode gcb-v2` against real Postgres + Chroma with an HF cache for `microsoft/graphcodebert-base@2b0488a7` (long; run detached).

## WU8 - Shared ScoringService (PR3, ~400 lines)

- [ ] 8.1 RED: `tests/test_backend_jaccard_parity.py` (root): backend Jaccard equals `models.graphcodebert.v2.baselines.jaccard_set` + `dedup.jaccard` on fixtures; skip if import fails (AS2.1 parity).
- [ ] 8.2 RED: `backend/tests/test_scoring_service.py`: raw A = max over references (0.3 vs 0.9 -> 0.9, argmax `reference_id`, ties -> lowest id); empty shingle stream does not raise; `SIN_REFERENCIA` with zero Chroma queries (AS2); abstained B -> `score_b` null, `ABSTENIDO`, `NO_EVALUABLE`, no 0.05 anywhere (AS3, CI8.1); client thresholds 0.01/0.01 have no effect and warn, `umbral_*` equal artifact values, in REAL and STUB (AS5.1, AS5.2, D9); `ALLOW_UNCALIBRATED` missing Jaccard calibration -> null flags, `NO_EVALUABLE` (AS4.3); pinned `referencia_id` from another problem -> 422.
- [ ] 8.3 RED: `backend/tests/test_api_flow.py` additions: same submission via `POST /analysis/run` and batch yields identical AS1.2 fields (AS1.2); batch persists decision indicators for flagged results (AS1.3); vector store returning 0.99 vs 0.0 leaves flags/dictamen equal and a raising store gives `gcb_similarity` null (AS8); no `CONFORMIDAD_BASE` indicator for `NO_EVALUABLE`/`SIN_REFERENCIA` (AS4.4); no module under `backend/app/` imports `models.fusion` (BF1.2).
- [ ] 8.4 GREEN: create `application/services/scoring_service.py` (`score`, `apply_outcome`, `build_indicators`), `infrastructure/lexical/jaccard.py` (via `asyncio.to_thread`), modify `application/orchestrator/analysis_orchestrator.py` and `application/services/batch_analysis_service.py` to delegate; delete the sigmoid/linear maps; dictamen NULL while `PENDIENTE`/`PROCESANDO`/`ERROR` (drop the `SIN_ALERTAS` placeholder); persist raw Jaccard in `similitud_semantica`, calibrated in `puntaje_calibrado_a`, `discrepancia_score` NULL (D8, D15); align batch decoding to `errors="replace"` (design risk).
- [ ] 8.5 Update existing backend tests whose assertions depended on the removed score maps (NF5). Full suite green.
- [ ] 8.6 Commit `feat(backend): shared ScoringService in single/async/batch`.

## WU9 - API fields, honest PDF, flag-driven XAI (PR4, ~350 lines)

- [ ] 9.1 RED: `backend/tests/test_reporting.py`: every AR1.1 field present, `calibracion_sha_a` equals manifest sha; abstained report has `score_b` null in JSON and non-empty `etiqueta_validacion`; legacy row (no new columns) returns `engine == "legacy"` with null provenance (AR1); PDF content model for abstained `NO_EVALUABLE` includes "ABSTENIDO" and the label, no "CONFORMIDAD" and no discrepancy row; unknown verdict never maps to CONFORMIDAD (AR3); XAI: `flag_a=False` -> no similarity alert, `flag_a=True` -> file-level `SIMILITUD_ARCHIVO` row with `reference_id`, heuristic rows labelled `origen: "heuristica"`, no synthetic-pattern alert when `flag_b` is false or B abstained (AR4).
- [ ] 9.2 GREEN: `presentation/schemas/analysis.py` (additive fields, Optional scores, computed `etiqueta_validacion`, `discrepancia_score` marked deprecated), `presentation/api/v1/endpoints/{analysis,problems}.py` (`threshold_*` Optional and ignored), `application/services/{xai_service,pdf_service}.py` (`extract_explanations(code, language, outcome)`).
- [ ] 9.3 Commit `feat(backend): API fields, honest PDF, flag-driven XAI`.

## WU10 - Frontend (PR4, ~400 lines)

- [ ] 10.1 RED: add a pytest static scan `backend/tests/test_frontend_contract.py` (SHOULD, AR2): `frontend/src` contains no `62`/`85` fallback literals in `SimilarityReportModal.tsx`, no `threshold_sem`/`threshold_ai` sent from `api.ts`, no `discrepancia` rendered as a result, no verdict else-branch mapping to "Conforme".
- [ ] 10.2 GREEN: `frontend/src/lib/api.ts` (nullable types, new fields, `analysis.run(entregaId, referenciaId?, asyncMode?)`), new `frontend/src/lib/dictamen.ts` (maps all six verdicts; null -> "Pendiente"; unknown -> "No evaluable"), `frontend/src/lib/demoData.ts` (new shape, visibly labelled demo, AR2.4), `pages/SimilarityReportModal.tsx` (remove fallbacks, `overallScore > 70` verdict and discrepancy row; show Channel A method "Jaccard léxico, 5 tokens" + threshold + key, B abstention badge, GCB "Exploratorio, zero-shot, no decide", STUB badge, label "No validado contra plagio derivado de la referencia"; null -> dash), `pages/NewComparisonModal.tsx` (caller at ~line 101 drops thresholds), `pages/Biblioteca.tsx`, `components/xai/EvidenceDrawer.tsx` (`?? 3` -> dash, heuristic label), `components/layout/ReferenceCard.tsx`.
- [ ] 10.3 `npm run lint` and `npm run build` in `frontend/` pass; full pytest suite green.
- [ ] 10.4 Commit `feat(frontend): nullable reports, verdict mapping, labels, no thresholds`.

## WU11 - Fusion note and figures (PR5, ~200 lines)

- [ ] 11.1 RED: `tests/test_generate_tt_figures.py`: tmp `runs/` tree with fixture `metrics.json` -> loader returns fixture values; no runs -> clear error, not defaults; no hardcoded metric literals in the script (SC1.1).
- [ ] 11.2 GREEN: `scripts/generate_tt_figures.py` (`--charcnn-run`, `--gcb-run` required; CharCNN figures from `metrics.json` + `history.csv`; Channel A bars from `runs/graphcodebert/<run>/{v2,v2_nodfg,jaccard,winnowing,legacy}__all/metrics.json`; remove `base_scores`/`lora_scores`/`p_ai` literals and the legacy `models.char_cnn.train` import).
- [ ] 11.3 `models/fusion.py`: module docstring "research-only, not on the runtime decision path"; no config or default changes (BF1.1).
- [ ] 11.4 Docs: update `CLAUDE.md` Architecture notes only if the settings/readiness behavior changes the documented commands (keep short); add a rollout section to `models/deploy/README.md` (order: build artifacts -> deploy backend -> `apply_migrations.py` -> reindex; HF cache volume or pre-download).
- [ ] 11.5 Commit `docs(backend): fusion note, figures from runs metrics` (use `chore` if no docs change dominates).

## Closing tasks (parent)

- [ ] C.1 **[PARENT]** Docker E2E: needs Docker running. `docker compose up --build` with `INFERENCE_MODE=REAL`; check `/health` `inference_ready=true` and per-channel keys/shas; run `apply_migrations.py`, reindex (7.6); analyze one submission single and batch, compare AS1.2 fields; confirm a tampered artifact gives 503 with no rows. Record evidence in the verify report.
- [ ] C.2 Final full suite: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider` (0 failures) plus frontend lint/build.

## Decisions Needed

- D-A (blocks WU2.1): confirm the parent will run the artifact build (full val scoring is long). Default: parent runs it detached; writer only commits the outputs.
- D-B (non-blocking, default chosen): channel state strings. Spec uses `EVALUADO`/`NO_CALIBRADO`/`ABSTENIDO`, design uses `OK`/`SIN_CALIBRACION`/`ABSTENCION`. Default: spec strings for persisted/API values (spec is the contract), mapped from the design matrix in one constant. Also assumed (design open questions): a positive flag wins over a non-evaluable other channel; GCB load failure blocks readiness unless `GCB_SECONDARY_ENABLED=false`.

## Risks

- WU8 is the bottleneck: it depends on 4, 5, 6 and 7, and carries the largest test surface. Keep WU4-7 green and merged before starting it.
- Isotonic Jaccard on 174 val positives gives coarse plateaus; achieved FPR and TPR may differ markedly from raw 0.845 (recorded in the manifest, shown in the UI).
- WU2 depends on a long parent-run job and on `runs/` artifacts that are gitignored; a missing run blocks WU2 and everything real-shape after it.
- Stop-on-error migrations may expose old non-idempotent statements (6.3).
- Docker E2E (C.1) and reindex (7.6) need Docker/HF cache and are outside pytest.
