# Spec: backend-model-integration (SDD-4)

Keywords follow RFC 2119. Scenarios MUST be testable with pytest in `backend/tests/` (in-memory SQLite, `StubInferenceEngine`, in-memory vector store) or `tests/`. Tests MUST NOT need real weights, Postgres or ChromaDB. Artifacts are tiny fake fixtures built in `tmp_path` (a checkpoint stand-in, `graphito.calibration/v1` JSON files, a manifest with matching sha256). Frontend has no test runner: frontend requirements are verified by `npm run lint`, `npm run build` and backend contract tests on the fields; static source scans in pytest are allowed (SHOULD).

Consumed unchanged: `models.evaluation` (`build_calibration`, `load_calibration`, `validate_calibration`, `graphito.calibration/v1`, shingle/Jaccard/`normalize` helpers, `split_v1`), CharCNN v2 result keys `score`/`abstained` (fix-charcnn-implementation CI4/CI5), `GraphCodeBERT` v2 facade (`input_version`, `pooling`; fix-graphcodebert-dfg-input GE7). Terms: A = Channel A (max 5-token-shingle Jaccard against the problem's references); B = Channel B (CharCNN v2); GCB = GraphCodeBERT v2 zero-shot cosine, secondary only. Threshold entries with `threshold: null` are `unachievable` (EM3.4).

## Capability: deployed-model-artifacts (new)

### DA1. Deploy directory and manifest
- DA1.1 The repository MUST track a deploy artifacts directory (name chosen in design) holding the CharCNN v2 checkpoint, the CharCNN calibration, the Jaccard calibration and a manifest. Weights MUST NOT be tracked beyond what the directory needs; `models/char_cnn/best_model.pth` MUST NOT be read, copied over or written.
- DA1.2 The manifest MUST list, per artifact: relative path, `sha256`, channel, source run id (the `runs/...` directory it came from), and the threshold keys: `fpr_0.01` for CharCNN and `fpr_0.05` for Jaccard. Paths MUST be relative to the manifest and MUST NOT escape the directory.
- DA1.3 `docker-compose.yml` MUST mount the directory read-only for the backend.

### DA2. Jaccard calibration artifact
- DA2.1 The Jaccard calibration MUST be a `graphito.calibration/v1` file, `method` isotonic, `channel` Jaccard/A, `fit_set.split == "val"`, produced by `build_calibration` over `split_v1` val scores. `fpr_0.05` MUST be present with a non-null threshold.
- DA2.2 A test MUST fail if the artifact's `fit_set.split` is not `val` or its manifest sha256 differs from the `split_v1` manifest hash recorded in the CharCNN calibration.

### DA3. Settings and loading
- DA3.1 `config.py` MUST add `CHARCNN_CHECKPOINT`, `CHARCNN_CALIBRATION`, `CHARCNN_THRESHOLD_KEY` (default `fpr_0.01`), `CHANNEL_A_METHOD` (default `jaccard`), `CHANNEL_A_CALIBRATION`, `CHANNEL_A_THRESHOLD_KEY` (default `fpr_0.05`), `GCB_INPUT_VERSION` (default `v2`), `ALLOW_UNCALIBRATED` (default false). Names are case-sensitive.
- DA3.2 The loader MUST verify, at load, that every manifest sha256 equals the sha256 of the file on disk, that each calibration validates against the schema, that the configured threshold key exists in its calibration with a non-null threshold, and that the manifest threshold keys equal the configured keys. Any failure MUST raise a typed artifact error and MUST NOT yield a partially loaded bundle.
- DA3.3 Applying a calibration MUST use numpy only (no scikit-learn, no torch import). `transform` of the loaded isotonic calibration on a fixed vector MUST equal the eval-side expected values within 1e-9.
- DA3.4 The loaded bundle MUST expose, per channel: calibrator, threshold value, threshold key, calibration sha256; and for B the checkpoint sha256. These feed AR1.
- DA3.5 `ALLOW_UNCALIBRATED=true` MUST be honoured only when `INFERENCE_MODE=REAL` is explicitly combined with it for development. The production compose profile MUST NOT set it true.

Scenarios
- Given valid fake artifacts and a matching manifest, When loaded, Then the bundle exposes both thresholds and all shas.
- Given a manifest sha256 that does not match the file, a missing file, a calibration with an unknown schema, a missing `fpr_0.05`, or a `null` (unachievable) threshold, When loaded, Then a typed error is raised and no bundle is returned.
- Given `CHANNEL_A_THRESHOLD_KEY=fpr_0.01` while the manifest says `fpr_0.05`, Then loading fails.
- Given the loader module, Then importing it does not import sklearn or torch.

## Capability: analysis-scoring (new)

### AS1. Single scoring service
- AS1.1 One scoring function (service) MUST produce channel scores, states, flags, thresholds and dictamen for a submission. The single-analysis orchestrator and the batch service MUST both call it; neither MAY contain its own score mapping (the sigmoid and linear maps are removed).
- AS1.2 For the same code, problem and engine state, single and batch paths MUST return identical `score_a`, `score_b`, `flag_a`, `flag_b`, `estado_canal_a/b`, `umbral_a/b`, `dictamen`, `reference_id` and provenance (ids and timestamps excepted).
- AS1.3 The batch path MUST persist decision indicators exactly as the single path does.
- AS1.4 The decision MUST NOT read Chroma, GCB or `discrepancia_score`.

### AS2. Channel A (Jaccard)
- AS2.1 Raw A MUST be the maximum Jaccard over 5-token shingles (eval helpers, after `normalize`) between the submission and every reference of the submission's problem, read from Postgres reference code. `reference_id` MUST be the argmax; ties MUST resolve to the lowest reference id. A submission with no shingles MUST follow the helper's convention and MUST NOT raise.
- AS2.2 Calibrated A = isotonic `transform(raw)`. `flag_a` is true iff calibrated A >= the `fpr_0.05` threshold from the artifact.
- AS2.3 When the problem has no references, `estado_canal_a` MUST be `SIN_REFERENCIA`, `score_a` and `flag_a` null, no Chroma query MUST be made for A, and the result MUST NOT be reported as `SIN_ALERTAS` on A's account.

### AS3. Channel B (CharCNN v2)
- AS3.1 B MUST consume `score`/`abstained` from the v2 result, never `ai_probability`, `prob_sintetico` or `confidence`. Calibrated B = calibration `transform(score)`; `flag_b` is true iff calibrated B >= the `fpr_0.01` threshold (0.1715 in the deployed artifact).
- AS3.2 When `abstained` is true: `score_b` null, `flag_b` null, `estado_canal_b == ABSTENIDO`. The numeric legacy keys MUST NOT be used as a stand-in.

### AS4. Decision matrix (calibrated flags only)
- AS4.1 Channel states: A in `{EVALUADO, SIN_REFERENCIA, NO_CALIBRADO}`, B in `{EVALUADO, ABSTENIDO, NO_CALIBRADO}`. The dictamen MUST be derived only from `flag_a`, `flag_b` and these states by this table (precedence top to bottom):

| flag_a | flag_b / B state | dictamen |
|---|---|---|
| true | true | `DISCREPANCIA_DUAL` |
| true | false, or B `ABSTENIDO` | `REVISION_SEMANTICA` |
| false or A `SIN_REFERENCIA` | true | `REVISION_ESTILOMETRICA` |
| false or A `SIN_REFERENCIA` | B `ABSTENIDO` | `NO_EVALUABLE` |
| `SIN_REFERENCIA` | false | `SIN_REFERENCIA` |
| false | false | `SIN_ALERTAS` |

- AS4.2 Enum values `NO_EVALUABLE` and `SIN_REFERENCIA` are new; existing values keep their strings.
- AS4.3 With `ALLOW_UNCALIBRATED=true` and a missing calibration for a channel, raw scores MUST be reported, `flag_a`/`flag_b` MUST be null, the channel state MUST be `NO_CALIBRADO`, the dictamen MUST be `NO_EVALUABLE`, and the response MUST say the result is uncalibrated. Without the setting, a missing calibration is an AS6 failure.
- AS4.4 Indicators MUST be created only for true flags; no `CONFORMIDAD_BASE` indicator MAY be fabricated for `NO_EVALUABLE` or `SIN_REFERENCIA`.

Scenarios (one per table row)
- Given calibrated flags (T,T), (T,F), (T, abstained), (F,T), (SIN_REF,T), (F, abstained), (SIN_REF, abstained), (SIN_REF,F), (F,F), When scored, Then the dictamen is DUAL, SEMANTICA, SEMANTICA, ESTILOMETRICA, ESTILOMETRICA, NO_EVALUABLE, NO_EVALUABLE, SIN_REFERENCIA, SIN_ALERTAS respectively, and `score_b` is null with `estado_canal_b == ABSTENIDO` whenever B abstained.
- Given a submission of `"int x;"` and a fake v2 engine returning `abstained=True` with `prob_sintetico=0.05`, Then no value 0.05 appears in the report and the dictamen is `NO_EVALUABLE` when A is not flagged.
- Given two references with Jaccard 0.3 and 0.9, Then raw A is 0.9 and `reference_id` is the second one; given an equal tie, Then the lower id.
- Given the same submission via `POST /analysis/run` and via batch upload, Then every AS1.2 field is equal.
- Given a batch run, Then decision indicators exist for flagged results.
- Given `ALLOW_UNCALIBRATED=true` without the Jaccard calibration, Then flags are null and the dictamen is `NO_EVALUABLE`.

### AS5. Thresholds
- AS5.1 In REAL mode, thresholds sent by the client (`threshold_sem`, `threshold_ai` or equivalent) MUST be ignored, never reach the decision, and the response MUST report the artifact thresholds as `umbral_a`/`umbral_b`.
- AS5.2 Client-supplied thresholds MUST be ignored in every mode (design D8); in STUB mode (development only) the service uses fixed default thresholds; the result MUST carry `engine == "stub"` and no `calibracion_sha_*` or `checkpoint_sha_b`.

Scenarios
- Given REAL mode (fake engine) and a request with thresholds 0.01/0.01, Then flags and dictamen are identical to the same request with no thresholds, and `umbral_*` equal the artifact values.

### AS6. Fail closed in REAL mode
- AS6.1 `INFERENCE_MODE=REAL` MUST NOT fall back to the stub engine for any reason (missing weights, import error, bad checkpoint, artifact error, missing calibration without AS4.3). `real_engine.py` MUST NOT construct or import the stub engine, and MUST NOT pass an adapter path to GCB.
- AS6.2 When the engine or artifacts are not ready, startup MUST NOT crash silently: the app starts, logs a typed reason, and the health endpoint MUST report `inference_ready: false`, `engine` and a reason code (no filesystem paths). Analysis endpoints (single, batch, reference creation that needs embeddings) MUST return 503 before writing anything.
- AS6.3 On any such failure nothing MUST be written to Postgres (reports, batch rows beyond what was already committed) or Chroma.
- AS6.4 Health MUST report `inference_ready: true` and the engine label only when the bundle loaded and verified (DA3.2).

Scenarios
- Given REAL mode with a corrupted artifact, When `GET` health, Then `inference_ready` is false; When running an analysis, Then the status is 503, the reports table is unchanged and the vector store `upsert` was never called.
- Given REAL mode and an engine whose construction raises, Then `get_inference_engine()` raises and no stub instance is created (spy).

### AS7. STUB mode
- AS7.1 The stub engine MUST be selected only by `INFERENCE_MODE=STUB`. Every result it produces MUST carry `engine == "stub"` in API, DB and report.

### AS8. GCB secondary signal
- AS8.1 `gcb_similarity` (cosine of v2 embeddings against the problem's references in the fingerprinted collection, maximum) MUST be reported as exploratory and zero-shot. It MUST NOT change flags, states or dictamen in any case.
- AS8.2 If GCB or Chroma is unavailable or raises, the analysis MUST still complete, `gcb_similarity` MUST be null, and nothing MUST be invented. (This does not relax AS6 for A/B artifacts.) At startup, a GCB model or collection that fails to load MUST keep the service not ready unless `GCB_SECONDARY_ENABLED=false` explicitly disables the secondary signal (then `gcb_similarity` is always null); AS8.2 covers per-request runtime errors.

Scenarios
- Given two runs identical except for the vector store returning 0.99 vs 0.0, Then the dictamen and flags are equal.
- Given a vector store that raises, Then the analysis completes with `gcb_similarity` null.

### AS9. Non-blocking inference
- AS9.1 Torch inference (CharCNN, GCB) MUST run off the event loop (thread pool or equivalent).

Scenario
- Given an engine whose `predict` sleeps 0.3 s, When two analyses run concurrently with a ticker coroutine, Then the ticker advances while they run.

## Capability: analysis-reporting (new)

### AR1. API fields (additive)
- AR1.1 Every report (single, batch item, history/detail) MUST add: `engine`, `canal_a_metodo`, `estado_canal_a`, `estado_canal_b`, `flag_a`, `flag_b`, `umbral_a`, `umbral_b`, `calibracion_sha_a`, `calibracion_sha_b`, `checkpoint_sha_b`, `gcb_similarity`, `reference_id`, model versions (CharCNN `arch_version`/`preproc_version`, GCB `input_version`/`pooling`) and `etiqueta_validacion`. Existing fields MUST keep names and types, except where AR1.2 and AR1.3 apply.
- AR1.2 `score_a` and `score_b` (the score columns, `models.py:161-162`) MUST be nullable in model, schema and responses; null means not evaluated, never 0.
- AR1.3 `discrepancia_score` MUST be nullable and, when present, carry a "not validated" label. The decision MUST NOT use it. New reports SHOULD return null.
- AR1.4 `etiqueta_validacion` MUST state that the scores are not validated against reference-derived plagiarism (calibrated on student-vs-student data). It MUST be present on every report, including `NO_EVALUABLE`.
- AR1.5 Legacy rows (no provenance) MUST be returned with `engine == "legacy"`, provenance fields null, and MUST NOT be rescored.

Scenarios
- Given a REAL-mode (fake) report, Then every AR1.1 field is present and `calibracion_sha_a` equals the manifest sha.
- Given an abstained report, Then `score_b` is null in the JSON (not 0 or absent) and `etiqueta_validacion` is non-empty.
- Given a legacy row inserted without the new columns, Then the API returns `engine == "legacy"` and null provenance.

### AR2. Frontend (verified by lint, build and static scan)
- AR2.1 `frontend/src/lib/api.ts` MUST stop sending thresholds. `SimilarityReportModal` and other components MUST NOT contain invented fallback values (the 62/85 literals) and MUST NOT map an unknown verdict to "Conforme".
- AR2.2 `NO_EVALUABLE`, `SIN_REFERENCIA` and unknown/null verdicts MUST render as "no evaluable" (or "sin referencia" for the latter), with a null score shown as a dash, never as 0%.
- AR2.3 The UI MUST show Channel A's method, the engine (with a visible stub marker), calibration state, the GCB signal labelled "exploratory, zero-shot" and the AR1.4 label. It MUST NOT show `discrepancia_score` as a result.
- AR2.4 `IS_DEMO_MODE` mock data MAY remain but MUST be visibly labelled demo.

### AR3. PDF
- AR3.1 The report PDF MUST print: Channel A method, calibration state and thresholds, B abstention when applicable, engine, the AR1.4 label, and `NO_EVALUABLE`/`SIN_REFERENCIA` as such. It MUST NOT fall back to `CONFORMIDAD` for unknown verdicts and MUST NOT include a discrepancy row.
- AR3.2 Tests MUST assert on extracted PDF text if the PDF library allows it, otherwise on the content model handed to the renderer.

Scenarios
- Given an abstained `NO_EVALUABLE` report, Then the PDF content includes "ABSTENIDO", the label and no "CONFORMIDAD" nor "discrepancia".

### AR4. XAI
- AR4.1 Rule-based XAI output MUST be labelled as heuristic (a field such as `origen: "heuristica"` and a UI label), never as model output.
- AR4.2 XAI MUST add a file-level similarity row driven by `flag_a`: present with the calibrated value and `reference_id` when flagged; absent or marked not evaluated otherwise. It MUST NOT assert similarity when `flag_a` is false/null.
- AR4.3 Heuristic rows MUST NOT contradict decision flags (no "synthetic pattern" alert when `flag_b` is false or B abstained).

Scenarios
- Given `flag_a == False`, Then the XAI payload has no similarity alert; given `flag_a == True`, Then it has the row with `reference_id`.

## Capability: reference-indexing (new)

### RI1. Embed before commit
- RI1.1 Creating or updating a reference MUST compute its embedding first. If embedding fails, the request MUST fail (503 in REAL) with no DB row and no Chroma entry. A fake or placeholder embedding MUST NOT ever be written (`problem_service.py:71-85` behaviour removed).
- RI1.2 If the Chroma write fails after embedding, the DB transaction MUST NOT commit. If the DB commit fails after the Chroma write, the Chroma entry SHOULD be removed.

### RI2. Fingerprinted collection
- RI2.1 The GCB collection name MUST derive from the embedding fingerprint: model id, `input_version`, pooling. Changing any component MUST select a different collection.
- RI2.2 The legacy collection MUST NOT be read, written or deleted by the new code, and the reindex script MUST NOT touch it.
- RI2.3 A reindex script MUST read reference code from Postgres, embed, and upsert into the fingerprinted collection, idempotently (rerun yields the same ids/count), reporting counts and failures, and exit non-zero on any failure.

### RI3. Strict adapter
- RI3.1 `chroma_adapter` MUST raise on client or query errors (no `[]` on error) and MUST raise when a returned result lacks `distances` (no similarity 1.0 default).
- RI3.2 An empty collection (no references) is a valid empty result, distinct from an error.

Scenarios
- Given an embedder that raises, When creating a reference, Then no DB row and no upsert exist.
- Given fingerprints differing only in pooling, Then collection names differ; given a legacy collection with documents, Then after reindex its count is unchanged.
- Given a query result without distances, Then the adapter raises; given a failing client, Then it raises, not `[]`.
- Given the reindex run twice, Then the collection count is the same.
- Given a vector store test double, Then it returns non-constant similarities (so tests cannot pass on a constant).

## Capability: charcnn-inference (modified)

### CI8.1 (replaces fix-charcnn-implementation CI8.1)
- CI8.1 The backend MUST consume the v2 keys `score` and `abstained` (AS3), never the legacy numeric keys, for any decision or reported score. Legacy keys MUST remain in the inference result unchanged (CI4.1); existing scripts keep working. `real_engine.py` is changed by this spec.

Scenario
- Given a v2 result with `abstained=True` and legacy `ai_probability=0.05`, Then no backend output contains 0.05 as a score.

## Capability: bimodal-fusion (modified)

### BF1. Research-only
- BF1.1 `models/fusion.py` MUST be documented (module docstring) as research-only and not on the runtime decision path. Config field names and defaults MUST be unchanged.
- BF1.2 A test MUST assert that no module under `backend/app/` imports `models.fusion`.

## Schema and migration

### MG1. Migration
- MG1.1 `backend/migrations/migration_features.sql` MUST make `similitud_semantica`, `probabilidad_ia` and `dictamen` nullable, add columns `puntaje_calibrado_a`, `engine`, `estado_canal_a`, `estado_canal_b`, `flag_a`, `flag_b`, `umbral_a`, `umbral_b`, `calibracion_sha_a`, `calibracion_sha_b`, `checkpoint_sha_b`, `canal_a_metodo`, `gcb_similarity` (all nullable), and `ALTER TYPE ... ADD VALUE IF NOT EXISTS` for `NO_EVALUABLE` and `SIN_REFERENCIA`. Each statement MUST be separate and idempotent; enum additions MUST NOT be inside a transaction block.
- MG1.2 Existing rows MUST be marked `engine = 'legacy'` where `engine` is null; their scores MUST NOT be altered.
- MG1.3 `apply_migrations.py` MUST stop at the first failing statement, exit non-zero, and run no later statement. A failure MUST NOT be swallowed or logged as success.
- MG1.4 `models.py` and `create_all` MUST define the same columns for fresh databases (SQLite tests).

Scenarios
- Given an executor double failing on statement 3, Then statements 4+ are not executed and the exit code is non-zero.
- Given the SQL file, Then each enum addition uses `IF NOT EXISTS` and the file is applicable twice (statement set idempotent, checked by static parse).
- Given an in-memory DB created via `create_all`, Then a report with null scores and `NO_EVALUABLE` persists and round-trips.

## Scripts

### SC1. Figures
- SC1.1 `scripts/generate_tt_figures.py` MUST read metrics from `runs/*/metrics.json` (latest run per channel, or paths given by argument) and MUST NOT contain hardcoded metric values. A missing run MUST be a clear error, not a default.

Scenario
- Given a tmp `runs/` tree with a fixture `metrics.json`, When the script's loader runs, Then returned values equal the fixture; given none, Then it raises.

## Non-functional requirements

- NF1. `models/evaluation/*` APIs and files MUST remain unchanged; only the CLI is used to produce DA2.
- NF2. `models/char_cnn/best_model.pth` MUST NOT be modified, and no promote CLI is run. No code path in the backend opens it for writing.
- NF3. No new runtime dependency beyond numpy for calibration apply; backend requirements MUST NOT add scikit-learn, and `peft` MUST NOT be imported on the backend path.
- NF4. The legacy Chroma collection and legacy DB rows MUST NOT be deleted or rescored.
- NF5. `INFERENCE_MODE=STUB` MUST keep a running system without artifacts (rollback path); existing backend tests SHOULD keep passing after updating assertions that depended on the removed score maps.
- NF6. The suite `pytest tests/ backend/tests/` SHOULD complete on CPU without GPU, network or weights; `npm run lint` and `npm run build` MUST pass.
