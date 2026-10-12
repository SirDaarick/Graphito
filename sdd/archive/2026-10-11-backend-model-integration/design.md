# Design: Backend Model Integration (backend-model-integration)

## Technical Approach

The backend gets one decision path built only from the validated SDD-1..3 artifacts. A build script copies the CharCNN v2 checkpoint and calibration from `runs/`, fits the Channel A Jaccard calibration on val, and writes everything under `models/deploy/` with a sha256 manifest. At startup in REAL mode, an infrastructure loader verifies the manifest and loads the calibrations and models once. If anything fails, it marks the engine not ready and every scoring or indexing endpoint returns 503 before any write.

A new application `ScoringService` is the only code that scores, used by sync, async and batch analysis. Channel A is the max 5-token-shingle Jaccard over the problem's references, read from Postgres. Channel B is CharCNN v2 with abstention. A pure domain function turns the calibrated flags into the verdict. GraphCodeBERT v2 (mean pooling) is a non-deciding secondary signal served from a fingerprinted Chroma collection. Torch runs on a dedicated thread pool. Reporting (API, UI, PDF, XAI) shows only measured values plus method, engine, thresholds, calibration hashes and the "not validated against reference-derived plagiarism" label.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|----------|----------------------|-----------|
| D1 | Artifacts live in `models/deploy/` (inside the existing `./models:/models:ro` mount). JSON files are tracked by default. Add an exact exception `!models/deploy/channel_b/best.pth` to `.gitignore`, mirroring the existing `best_model.pth` one. | A separate `./artifacts` mount; Git LFS; loading straight from `runs/` | No compose volume change. `runs/` is gitignored and holds many runs. A single exact exception keeps `*.pth` ignored everywhere else. The user's `models/char_cnn/best_model.pth` is never touched. |
| D2 | `scripts/build_deploy_artifacts.py` is the only writer of `models/deploy/`. It consumes the `models.evaluation` APIs unchanged. It refuses to overwrite differing files without `--force`. | Manual copy; a promote CLI | Reproducible, records provenance, and needs no changes to `models/evaluation`. |
| D3 | Channel A calibration: val `plagiarism_pairs` (ambiguous excluded, same as the GCB eval). Score = `dedup.jaccard(shingle_hashes(token_ids(shingle_tokens(code))))`, scored per assignment block. Then `ScoredSet(ids="a\|b", split="val", manifest_sha256)` → `build_calibration(method="isotonic", targets=(0.05, 0.01))`. The script refuses (exit 1) if `fpr_0.05` is unachievable. | Platt/temperature; raw-space threshold from `thresholds_val.json` | This is the proposal's binding choice. Jaccard lies in [0,1], so isotonic validates. The raw val threshold (0.649, TPR 0.845) is recorded only as a sanity cross-check. |
| D4 | Hexagonal split. **Domain**: `domain/scoring.py` (pure dataclasses + `decide()`), `domain/errors.py`. **Ports**: `InferencePort` (reshaped), new `CalibrationPort` and `LexicalSimilarityPort`. **Infrastructure**: `infrastructure/artifacts/` (manifest + calibration loader, stub artifacts), `infrastructure/lexical/jaccard.py`, inference engines, Chroma adapter. **Application**: `application/services/scoring_service.py`. | Scoring inside the inference engine (today's `compute_decision`); application importing `models.*` | The decision must not depend on which engine runs. Only infrastructure touches the `models/` package (one `models_path.ensure_on_path()` helper, extracted from `real_engine.py:11-13`). |
| D5 | REAL readiness: the app **starts degraded** with `inference_ready=false` + `inference_error`. `require_inference_ready` (a FastAPI dependency) returns 503 on `POST /analysis/run`, `POST /analysis/batch` and `POST /problems/{id}/references`. No stub fallback exists anywhere in REAL. | Crashing at startup | Dependencies run before the handler, so nothing is written to Postgres or Chroma. `/health` can explain the failure, and compose `restart: unless-stopped` does not crash-loop. |
| D6 | Settings select paths and threshold keys. The manifest proves integrity. Every configured file must appear in the manifest with a matching sha256. The configured key must equal the manifest key and be achievable in the calibration file. Any mismatch → not ready. | Settings only; manifest only | Prevents silent drift between `.env` and the deployed files. Thresholds come only from calibration files, and `THRESHOLD_SEM/AI` are deleted. |
| D7 | `ALLOW_UNCALIBRATED` (default false) is honoured only when `APP_ENV != "production"`. A channel without calibration then still computes its raw score, but its state is `SIN_CALIBRACION` (no flag), and the engine reports `calibration_state=uncalibrated`. | Allowed in every environment | Answers the proposal's open question (development only). The validator refuses the combination at settings load. |
| D8 | Persisted scores. `similitud_semantica` = **raw** Jaccard (all existing "% similarity" displays stay meaningful). New `puntaje_calibrado_a` = isotonic output, the space where `umbral_a` lives. `probabilidad_ia` = **calibrated** CharCNN (Platt), the space of `umbral_b`. Flags are persisted, so no client recomputes a decision. | Calibrated A in `similitud_semantica` | Isotonic plateaus are not a similarity. Teachers read overlap; the decision reads flags. |
| D9 | Client `threshold_sem/ai` become `Optional`, are ignored in **both** modes, and trigger a warning log. The response carries the thresholds actually used. | Honouring them in STUB | One code path; the frontend stops sending them. |
| D10 | Inference runs on `ThreadPoolExecutor(max_workers=INFERENCE_WORKERS=1, thread_name_prefix="inference")` owned by the engine (`loop.run_in_executor`). Jaccard runs via `asyncio.to_thread`. Models load once in `lifespan` (also in a thread). | Lazy load on first request; default executor | The event loop is never blocked, and a single torch worker avoids CPU oversubscription. Batch `Semaphore(3)` stays and queues on the pool. |
| D11 | GCB v2 is a secondary signal. Errors (Chroma or model) give `gcb_similarity=NULL`, `gcb_estado="ERROR"` and a warning indicator. The verdict is unaffected. With `GCB_SECONDARY_ENABLED=true` (default), a failed GCB **load** makes the engine not ready (no fake embeddings). | Failing the whole analysis on Chroma errors; a stub fallback | The decision never depends on Chroma (proposal), and fakes are never written. |
| D12 | The Chroma collection name is `gcb_{input_version}_{pooling}_{fp[:12]}`. `fp` = sha256 of canonical JSON {model_name, model_revision, input_version, walker_version, pooling, use_dfg, code_length, data_flow_length, max_windows, dtype}. STUB uses `stub_{fp[:12]}`. The legacy collections `codigos_referencia` and `codigos_referencia_v2` are untouched. | Reusing `codigos_referencia_v2` | Embeddings from different pipelines never mix, and stub vectors can never reach a real collection. |
| D13 | Migration statements run one per transaction on an `AUTOCOMMIT` connection, stopping at the first error (exit 1). `ALTER TYPE dictamenenum ADD VALUE IF NOT EXISTS` statements are separate statements. | Today's single `engine.begin()` that swallows errors | In PG, one error aborts the transaction, so every later statement fails silently today. Autocommit also sidesteps "new enum value unusable in the same transaction". |
| D14 | `estado_canal_a/b` and `engine` are `VARCHAR`, not PG enums. Only `dictamenenum` gains values (it already exists). | New PG enum types | Fewer non-transactional DDL statements; easier to extend. |
| D15 | `discrepancia_score` is deprecated: always NULL for new rows, the API field is documented as deprecated, and the UI/PDF drop it. `models/fusion.py` gets a research-only module note. | Keeping `sim × prob` | It is unvalidated (proposal). |

## Decision Matrix (`domain/scoring.decide`)

Channel states. **A**: `OK`, `SIN_REFERENCIA` (problem has 0 references), `VACIO` (empty shingle stream), `SIN_CALIBRACION`. **B**: `OK`, `ABSTENCION` (CharCNN `abstained=True`), `SIN_CALIBRACION`. A channel is *evaluable* iff its state is `OK`, and only then is `flag = calibrated >= threshold`. Rule: a positive flag on an evaluable channel is never hidden. `SIN_ALERTAS` requires both channels evaluable and negative.

| A \ B | B OK, flag | B OK, no flag | B not evaluable |
|---|---|---|---|
| A OK, flag | DISCREPANCIA_DUAL | REVISION_SEMANTICA | REVISION_SEMANTICA |
| A OK, no flag | REVISION_ESTILOMETRICA | SIN_ALERTAS | NO_EVALUABLE |
| A SIN_REFERENCIA | REVISION_ESTILOMETRICA | SIN_REFERENCIA | SIN_REFERENCIA |
| A VACIO / SIN_CALIBRACION | REVISION_ESTILOMETRICA | NO_EVALUABLE | NO_EVALUABLE |

`dictamen` becomes nullable: NULL while `PENDIENTE`/`PROCESANDO`/`ERROR` (today's placeholder `SIN_ALERTAS` at `analysis_orchestrator.py:254` is dropped).

## Data Flow

    POST /analysis/run | batch worker | async task
          │  (require_inference_ready → 503 before any write)
          ▼
    ScoringService.score(db, entrega, referencia_id?)
      ├─ refs = SELECT codigos_fuente WHERE problema_id AND tipo=REFERENCIA  (or the pinned ref; 422 if other problem)
      ├─ A: to_thread(Jaccard(entrega, ref) for ref) → argmax (ties: created_at, id) → CalibrationPort.a.apply/threshold
      ├─ B: engine pool → CharCNN v2 {score, abstained} → CalibrationPort.b.apply/threshold
      ├─ GCB: engine pool → embedding → Chroma[gcb_v2_mean_<fp>].query(problema_id, top_k=1)   (non-deciding)
      └─ decide(A, B) → ScoringOutcome
          ▼
    apply_outcome(reporte, outcome) + build_indicators(outcome) + XAIService(outcome) → commit

    POST /problems/{id}/references: embed (pool) → add row (explicit uuid4) → flush → Chroma upsert
          → commit; upsert error → rollback + 503; commit error → delete_reference (compensation)

## Deploy Manifest (`models/deploy/manifest.json`, schema `graphito.deploy-manifest/v1`)

```json
{"schema": "graphito.deploy-manifest/v1",
 "build": {"script": "scripts/build_deploy_artifacts.py", "git_sha": "…", "dirty": false},
 "split_manifest_sha256": "e835362d…",
 "label": "not validated against reference-derived plagiarism",
 "files": {"channel_a/calibration.json": "<sha256>", "channel_b/best.pth": "<sha256>", "channel_b/calibration.json": "<sha256>"},
 "channel_a": {"method": "jaccard", "shingle_k": 5, "calibration": "channel_a/calibration.json", "calibration_method": "isotonic",
               "threshold_key": "fpr_0.05", "threshold": 0.0, "achieved_fpr": 0.0, "tpr": 0.0,
               "source_run": "graphcodebert/20261011-082155", "raw_val_threshold_ref": 0.6491},
 "channel_b": {"method": "charcnn_v2", "checkpoint": "channel_b/best.pth", "calibration": "channel_b/calibration.json",
               "calibration_method": "platt", "threshold_key": "fpr_0.01", "threshold": 0.1715,
               "arch_version": 2, "preproc_version": 2, "source_run": "char_cnn/20261011-015734"},
 "gcb": {"role": "secondary_non_deciding", "model_name": "microsoft/graphcodebert-base", "model_revision": "2b0488a7…",
         "input_version": "v2", "pooling": "mean", "walker_version": "c-cpp-2", "fingerprint": "<sha256>",
         "source_run": "graphcodebert/20261011-082155"}}
```

Settings (`config.py`): `DEPLOY_MANIFEST=models/deploy/manifest.json`, `CHANNEL_A_METHOD=jaccard`, `CHANNEL_A_CALIBRATION`, `CHANNEL_A_THRESHOLD_KEY=fpr_0.05`, `CHARCNN_CHECKPOINT`, `CHARCNN_CALIBRATION`, `CHARCNN_THRESHOLD_KEY=fpr_0.01`, `GCB_INPUT_VERSION=v2`, `GCB_POOLING=mean`, `GCB_SECONDARY_ENABLED=true`, `INFERENCE_WORKERS=1`, `ALLOW_UNCALIBRATED=false`, `APP_ENV=development`. Relative paths resolve against the project root (`/` in the container, so `/models/deploy/...`). `/health` adds `engine`, `inference_ready`, `inference_error`, `calibration_state`, and `artifacts` {manifest sha, per-channel key, threshold, calibration sha}.

## Interfaces / Contracts

```python
# domain/scoring.py (no framework imports)
@dataclass(frozen=True)
class ChannelResult:
    estado: str                    # OK | SIN_REFERENCIA | VACIO | ABSTENCION | SIN_CALIBRACION
    raw: float | None; calibrated: float | None; flag: bool | None
    threshold: float | None; threshold_key: str | None; calibration_sha256: str | None

# domain/ports
class InferencePort(ABC):          # compute_decision and generate_hybrid_embedding removed
    engine: str                    # "real" | "stub"
    embedding_fingerprint: str
    def readiness(self) -> Readiness: ...                          # ready, reason, details
    async def extract_semantic_embedding(self, code, lang) -> list[float]: ...   # GCB v2, 768; raises InferenceError
    async def predict_stylometry(self, code) -> StylometryResult: ...            # raw_score | None, abstained
class CalibrationPort(ABC):
    def channel(self, name: Literal["a", "b"]) -> ChannelCalibration | None: ...  # apply(x), threshold, key, sha256
class LexicalSimilarityPort(ABC):
    def similarity(self, code_a: str, code_b: str) -> float | None: ...         # None when the submission stream is empty
```

API (`ReporteAnalisisResponse`, additive; existing score fields become `Optional`): `similitud_semantica`, `probabilidad_ia`, `discrepancia_score` (deprecated), `dictamen` nullable; new `engine`, `canal_a_metodo`, `estado_canal_a`, `estado_canal_b`, `flag_a`, `flag_b`, `umbral_a`, `umbral_b`, `puntaje_calibrado_a`, `calibracion_sha_a`, `calibracion_sha_b`, `checkpoint_sha_b`, `manifest_sha`, `gcb_similarity`, `gcb_estado`, and the computed `etiqueta_validacion`. `DictamenEnum` += `NO_EVALUABLE`, `SIN_REFERENCIA`.

## Schema Migration (`backend/migrations/migration_features.sql`, section 8)

`ALTER COLUMN ... DROP NOT NULL` on `similitud_semantica`, `probabilidad_ia`, `discrepancia_score`, `dictamen`. `ADD COLUMN IF NOT EXISTS` (all nullable): `engine VARCHAR(20)`, `canal_a_metodo VARCHAR(30)`, `estado_canal_a/b VARCHAR(30)`, `flag_a/b BOOLEAN`, `umbral_a/b DOUBLE PRECISION`, `puntaje_calibrado_a DOUBLE PRECISION`, `calibracion_sha_a/b VARCHAR(64)`, `checkpoint_sha_b VARCHAR(64)`, `manifest_sha VARCHAR(64)`, `gcb_similarity DOUBLE PRECISION`, `gcb_estado VARCHAR(20)`. `ALTER TYPE dictamenenum ADD VALUE IF NOT EXISTS 'NO_EVALUABLE';` (and `'SIN_REFERENCIA'`). Legacy marking: `UPDATE reportes_analisis SET engine='legacy' WHERE engine IS NULL;` (idempotent; rows are never rescored). Order: backend start (`create_all`) first, then `python apply_migrations.py`. `apply_migrations.py` exposes a pure `split_statements()` and exits 1 on the first failure.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `scripts/build_deploy_artifacts.py` | Create | Jaccard val calibration, CharCNN copy, sha256 manifest (atomic, `--force`) |
| `models/deploy/**`, `.gitignore` | Create/Modify | Artifacts; `!models/deploy/channel_b/best.pth` |
| `backend/app/config.py` | Modify | D6/D7 settings; drop `THRESHOLD_SEM/AI` |
| `backend/app/main.py` | Modify | Lifespan builds engine + artifacts in a thread; `/health` readiness |
| `backend/app/domain/scoring.py`, `domain/errors.py`, `domain/ports/{inference,calibration,lexical_similarity}_port.py` | Create/Modify | Pure decision, errors, ports |
| `backend/app/infrastructure/{models_path.py,artifacts/,lexical/jaccard.py}` | Create | Path helper, manifest loader + stub artifacts, Jaccard adapter |
| `backend/app/infrastructure/inference/{__init__,real_engine,stub_engine}.py` | Modify | No fallback, pool, abstention, no adapter path, v2/mean, fingerprint; stub `engine="stub"` with abstention below the CharCNN minimum length |
| `backend/app/infrastructure/vector_store/{__init__,chroma_adapter}.py`, `vector_store_port.py` | Modify | Collection name injected; missing distance and errors raise `VectorStoreError` |
| `backend/app/application/services/scoring_service.py` | Create | `score`, `apply_outcome`, `build_indicators` |
| `backend/app/application/orchestrator/analysis_orchestrator.py`, `services/batch_analysis_service.py` | Modify | Delegate to `ScoringService`; delete the sigmoid/linear maps |
| `backend/app/application/services/{problem_service,xai_service,pdf_service}.py` | Modify | Embed before commit; flag-driven heuristic rows; honest PDF |
| `backend/app/presentation/{schemas/analysis.py,api/v1/deps.py,api/v1/endpoints/{analysis,problems}.py}` | Modify | Fields, `require_inference_ready`, `get_scoring_service` |
| `backend/app/infrastructure/database/models.py`, `backend/migrations/migration_features.sql`, `backend/apply_migrations.py` | Modify | Columns, enum, stop on error |
| `backend/reindex_chroma.py` | Modify | `--mode gcb-v2`: reembed Postgres references into the fingerprinted collection |
| `backend/tests/conftest.py`, `backend/tests/test_*.py`, `tests/test_backend_jaccard_parity.py` | Modify/Create | See Testing |
| `frontend/src/lib/{api.ts,dictamen.ts,demoData.ts}`, `pages/{SimilarityReportModal,NewComparisonModal,Biblioteca}.tsx`, `components/xai/EvidenceDrawer.tsx`, `components/layout/ReferenceCard.tsx` | Modify/Create | Nullable types, no thresholds, mapping, labels |
| `models/fusion.py` | Modify | Docstring: research-only |
| `scripts/generate_tt_figures.py` | Modify | Read `runs/*/metrics.json` |

## Reporting

- **Frontend**: `ReporteAnalisis` fields become `number | null`, plus the new fields. `api.analysis.run(entregaId, referenciaId?, asyncMode?)` drops the threshold params (caller `NewComparisonModal.tsx:101`). A new `lib/dictamen.ts` maps all six verdicts; null shows "Pendiente", and NO_EVALUABLE, SIN_REFERENCIA or unknown show "No evaluable" / "Sin referencia", never "Conforme". `SimilarityReportModal.tsx:408-415,451,701,952` loses the 62/85 fallbacks, the `overallScore > 70` verdict and the discrepancy row, and shows "—" for null. The UI shows: the Channel A method ("Jaccard léxico, 5 tokens") with the raw value plus threshold and key; Channel B with an abstention badge; GCB as "Exploratorio, zero-shot, no decide"; a STUB badge when `engine="stub"`; and the label "No validado contra plagio derivado de la referencia". The `?? 3` complexity fallback in `EvidenceDrawer` becomes "—". `demoData.ts` moves to the new shape.
- **PDF**: the verdict maps all states, and the else-branch `CONFORMIDAD` is used only for `SIN_ALERTAS`. The report prints engine, method, scores (or "No evaluable"), thresholds + keys, short calibration and checkpoint sha, abstention, the GCB secondary signal, the label, and the manifest sha. Discrepancy is dropped.
- **XAI**: `extract_explanations(code, language, outcome)`. Line rows are gated on `flag_a`/`flag_b` (not on 0.80/0.75) and relabelled "Heurística (no es salida del modelo)". A new file-level row (`numero_linea=None`, `categoria="SIMILITUD_ARCHIVO"`) gives the Jaccard value, reference author, threshold and flag.
- **Spec deltas**: CI8.1 now says the backend consumes `score`/`abstained` (raw score → Platt), not the legacy `prob_sintetico`. `bimodal-fusion` is research-only.

## Figures (`scripts/generate_tt_figures.py`)

The script takes `--charcnn-run` and `--gcb-run` (required). The CharCNN figures read `metrics.json` + `history.csv`. The Channel A comparison bars read `runs/graphcodebert/<run>/{v2,v2_nodfg,jaccard,winnowing,legacy}__all/metrics.json` (ROC-AUC, PR-AUC, MAP@R with CIs). Figures with no metrics source (the hardcoded `base_scores`/`lora_scores`/`p_ai` literals) are removed, not faked. The legacy `models.char_cnn.train` import goes away.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit (domain) | All 20 combinations of `decide()` (A: OK±, SIN_REFERENCIA, VACIO, SIN_CALIBRACION × B: OK±, ABSTENCION, SIN_CALIBRACION) | Table-driven, pure |
| Unit (infra) | Loader: ok / sha mismatch / missing file / key mismatch / unachievable / `ALLOW_UNCALIBRATED` in production refused | `fake_artifacts` fixture: tmp dir with valid `graphito.calibration/v1` JSON (isotonic identity), fake checkpoint bytes, real sha256 |
| Unit (infra) | Chroma: missing `distances` raises; client error raises; name from fingerprint | Fake collection object |
| Unit (infra) | Engine never runs torch on the loop thread | Fake model factories record `threading.current_thread().name` |
| Parity | Backend Jaccard == `models.graphcodebert.v2.baselines.jaccard_set` + `dedup.jaccard` | Root `tests/`, fixtures, skip if import fails |
| API | Single vs batch: same submission, identical scores/verdict; SIN_REFERENCIA; abstention → NO_EVALUABLE; client thresholds have no effect; not ready → 503 with zero rows and zero upserts; upsert failure → no reference row | `conftest`: project root on `sys.path`, `fake_artifacts`, a non-constant `InMemoryVectorStore` (real cosine, `fail` switch), stub engine with abstention |
| Migration | `split_statements`, stop-on-first-error exit code | Pure function + fake connection; manual run on compose Postgres 16 |
| Frontend | Types, removed fallbacks | `npm run lint` + `npm run build` (no runner) |

`test_thresholds.py` is rewritten: request thresholds are ignored, and the settings no longer define them.

## Work-Unit Commits and PR Slices (≈400 lines advisory)

| # | Commit | ~Lines | PR |
|---|--------|--------|----|
| 1 | `feat(eval): build_deploy_artifacts script` + tests | 300 | PR1 |
| 2 | `data(deploy): Jaccard calibration, CharCNN v2, manifest` | data | PR1 |
| 3 | `feat(backend): scoring domain, ports, decision matrix` | 250 | PR2 |
| 4 | `feat(backend): settings, artifacts loader, readiness, 503` | 350 | PR2 |
| 5 | `feat(backend): fail-closed real engine, thread pool, stub label` | 300 | PR2 |
| 6 | `feat(db): nullable scores, provenance columns, enum values, stop-on-error` | 200 | PR3 |
| 7 | `feat(backend): strict fingerprinted Chroma, embed-before-commit, reindex mode` | 300 | PR3 |
| 8 | `feat(backend): shared ScoringService in single/async/batch` + parity tests | 400 | PR3 |
| 9 | `feat(backend): API fields, honest PDF, flag-driven XAI` | 350 | PR4 |
| 10 | `feat(frontend): nullable reports, verdict mapping, labels, no thresholds` | 400 | PR4 |
| 11 | `docs/chore: fusion note, figures from runs metrics` | 200 | PR5 |

Each PR is green on its own (`pytest tests/ backend/tests/`; PR4 adds lint/build). Rollback = revert the PR. `INFERENCE_MODE=STUB` runs without artifacts.

## Migration / Rollout

Run in order: build artifacts (commit 2) → deploy the backend → `apply_migrations.py` → `python reindex_chroma.py --mode gcb-v2`. Mount an HF cache volume (or pre-download `microsoft/graphcodebert-base@2b0488a7`), or GCB load fails and REAL stays not ready. Legacy rows show `engine='legacy'` and are labelled as such in the UI and PDF.

## Risks

- Isotonic on 1.6M val pairs with 174 positives has coarse plateaus: the `fpr_0.05` calibrated threshold may give an achieved FPR well under target and a lower TPR than raw 0.845. Both are recorded in the manifest and shown.
- Text decoding differs between eval (`errors="replace"`) and batch upload (`errors="ignore"`, `analysis.py:190`). Align batch to `replace`.
- `stop-on-error` may expose legacy statements that were never idempotent on some DBs. They are reviewed in commit 6.
- The verdict precedence when one channel flags and the other is not evaluable (matrix rows 1/3/4) refines the proposal wording and must match the parallel spec.

## Open Questions

- [ ] Confirm the matrix precedence: a positive flag wins over the other channel being non-evaluable (assumed yes).
- [ ] Should a GCB load failure block readiness, or only disable the secondary signal? Assumed: it blocks (D11), with `GCB_SECONDARY_ENABLED=false` as the explicit opt-out.
