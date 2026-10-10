# Design: Validate Phase 1 - False-Positive Fixes (subset)

## Technical Approach

Five independent work units, ordered so each lands on a green test baseline: (1) reproducible test harness, (2) a 768-dim-only semantic index, (3) canonical thresholds in `Settings`, (4) a comment-aware CharCNN length guard, (5) a benchmark skeleton that runs on a synthetic fixture. Existing hexagonal layering stays as it is. The domain does not import `app.config`, and application or presentation code injects the settings values.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|----------|----------------------|-----------|
| D1 | Root `pytest.ini` (`pythonpath = . backend`, `testpaths = tests backend/tests`, registered markers) plus `tests/conftest.py` that auto-skips tests by availability probe: `requires_charcnn_weights` (`models/char_cnn/best_model.pth` exists), `requires_graphcodebert` (`AutoConfig.from_pretrained("microsoft/graphcodebert-base", local_files_only=True)` succeeds) | Per-file `sys.path.insert` hacks; env-var opt-in | One config makes `app` and `models` importable. Probes give deterministic pass/skip with no manual steps. |
| D2 | Keep `google-auth` (it is already in `backend/requirements.txt`) and also move its imports inside `AuthService.login_with_google`. On `ImportError`, return HTTP 503. | Dependency only; full removal | App import and test collection should not depend on one login provider. The 503 makes the failure explicit when someone actually logs in with Google. |
| D3 | `test_char_cnn_robustness.py` calls `pytest.importorskip("sklearn")`. A new root `requirements-dev.txt` (`-r backend/requirements.txt` + `scikit-learn`) declares it. | Add sklearn to the backend image | `models/char_cnn/train.py:26` imports sklearn. The backend runtime does not need it. |
| D4 | Index and query only `extract_semantic_embedding` (768 dims). Remove `hybrid_vector` in the orchestrator sync and async paths and in `batch_analysis_service.py:219`. `problem_service.py:71` indexes the semantic vector. | Keep 769 and zero the last dim | Cosine over `[sem..., ai_prob]` mixes the stylometry channel into Channel A similarity. This makes the Chroma path inconsistent with the `referencia_id` branch, which already uses 768. |
| D5 | New collection `codigos_referencia_v2` (metadata `hnsw:space=cosine`, `embedding_dim=768`). The adapter validates `len(embedding)==768` in `upsert` and `query` and raises `ValueError`. The legacy collection stays untouched. | In-place rewrite of `codigos_referencia` | Chroma fixes dimensionality per collection. Today a mismatch is swallowed and returns `[]`, so sim=0, a silent false negative. A versioned collection allows instant rollback. |
| D6 | `backend/reindex_chroma.py` (sits next to `apply_migrations.py`). `--mode slice` (default) copies legacy embeddings `[:768]` into v2, without models. `--mode reembed` recomputes from Postgres `REFERENCIA` rows through `get_inference_engine()`. Idempotent upsert. `--drop-legacy` is opt-in. | Auto-migrate at startup | `slice` is exact because index 768 was `ai_prob`. `reembed` covers a missing legacy collection or a changed model. An explicit script avoids hidden startup cost. At startup the adapter only logs a warning when legacy is non-empty and v2 is empty. |
| D7 | `Settings.THRESHOLD_SEM=0.85` and `THRESHOLD_AI=0.70` are canonical. `compute_decision` thresholds become keyword-only with no default (port, stub, real). `AnalysisRunRequest` uses `Field(default_factory=lambda: settings.THRESHOLD_SEM)`. The batch service, tests and scripts pass `settings.*`. | Domain constant; keep the defaults | Defaults in four places drifted (0.85 vs 0.75). Making the parameters required means a missing value fails loudly. Env override works. The sigmoid `baseline=0.85` in `calibrate_semantic_similarity` is a separate concept and is left alone. |
| D8 | Guard uses `CharPreprocessor.effective_length(text)`, defined as non-whitespace length after the existing `strip_c_comments`, applied unconditionally. The regex there already consumes string and char literals first, so `//` and `/*` inside literals are preserved. | New state machine | Reuses tested code. It needs no weights, so it can be unit-tested. Known limits: C++ raw strings `R"(...)"`, digit separators `1'000`, `//` comments with `\` continuation. |
| D9 | `data/golden_set/build_manifest.py` scans `<root>/<problem_id>/<class>/*.{c,cpp}` with class in `reference|original|copy|ai`. The split is `sha256(problem_id)` against `--test-ratio`, so a problem never spans two splits. `scripts/benchmark_suite.py` uses numpy-only AUC (Mann-Whitney), F1 and FPR. It takes `--engine stub|real` and reuses `calibrate_semantic_similarity` + `compute_decision`. | sklearn metrics; Chroma in the loop | No new runtime dependency. The benchmark measures the production decision path. In-memory top-1 per problem mirrors `query_nearest(top_k=1)`. |

## Data Flow (after D4/D5)

    submission -> extract_semantic_embedding (768) --+--> Chroma v2 query(problema_id) -> raw cos
                -> predict_synthetic_prob ----------|                                     |
                                                    +-> calibrate -> compute_decision(settings thresholds)

## File Changes

| File | Action | Change |
|------|--------|--------|
| `pytest.ini`, `tests/conftest.py`, `requirements-dev.txt` | Create | D1, D3 |
| `backend/app/application/services/auth_service.py` | Modify | Lazy Google imports, 503 (D2) |
| `tests/test_calibration_experiment.py`, `tests/test_escom_units.py`, `tests/test_char_cnn_robustness.py` | Modify | Markers, importorskip, `settings.THRESHOLD_SEM` |
| `tests/test_e2e_analysis.py` | Modify | Move the module-level `settings.*` mutation into `run_e2e_test`, so it no longer leaks into the session. Index 768. |
| `backend/app/application/orchestrator/analysis_orchestrator.py`, `services/batch_analysis_service.py`, `services/problem_service.py` | Modify | 768 vector (D4). Batch passes thresholds (D7). |
| `backend/app/infrastructure/vector_store/chroma_adapter.py` | Modify | v2 collection, dim guard, legacy warning (D5) |
| `backend/reindex_chroma.py` | Create | D6 |
| `backend/app/config.py`, `domain/ports/inference_port.py`, `inference/stub_engine.py`, `inference/real_engine.py`, `presentation/schemas/analysis.py` | Modify | D7. Port docstring: `generate_hybrid_embedding` deprecated and no longer used for indexing. |
| `scripts/benchmark_student_archetypes.py` | Modify | `settings.THRESHOLD_SEM` |
| `models/char_cnn/preprocess.py`, `models/char_cnn/inference.py` | Modify | D8 |
| `backend/tests/conftest.py` | Modify | `InMemoryVectorStore` records the last embedding and asserts dim 768 |
| `backend/tests/test_vector_dims.py`, `backend/tests/test_thresholds.py`, `tests/test_char_cnn_guard.py`, `tests/test_benchmark_suite.py` | Create | RED-first tests |
| `data/golden_set/build_manifest.py`, `data/golden_set/README.md`, `scripts/benchmark_suite.py`, `tests/fixtures/golden_set_tiny/**` | Create | D9 |

## Interfaces

Manifest (`data/golden_set/manifest.json`):
```json
{"version": 1, "created_at": "ISO-8601", "test_ratio": 0.3,
 "samples": [{"id": "p01/copy/a.c", "problem_id": "p01", "path": "p01/copy/a.c",
   "lang": "c", "role": "reference|submission", "label_copy": true, "label_ai": false,
   "split": "dev|test"}]}
```
Metrics output (`--out`, default `benchmark_suite_results.json`):
```json
{"engine": "stub", "manifest": "...", "threshold_ai": 0.70,
 "runs": [{"threshold_sem": 0.85, "split": "all|dev|test", "n": 12,
   "channel_a": {"auc": 0.9, "f1": 0.8, "fpr": 0.1, "tp": 4, "fp": 1, "tn": 6, "fn": 1},
   "channel_b": {}, "fused": {}}]}
```
Channel A: score = calibrated sim, label `label_copy`. Channel B: score = `ai_prob`, label `label_ai`. Fused: pred = `dictamen != SIN_ALERTAS`, label = `copy OR ai`, AUC score = `max(sem, ai)` (assumption). AUC is `null` when a split has only one class.

## Testing Strategy (test-first)

| Unit | RED test | GREEN check |
|------|----------|-------------|
| 1 | `pytest tests/ backend/tests/` currently fails at collection | Exits 0 with only pass or skip |
| 2 | `test_vector_dims`: reference upsert and `/analysis/run` query embeddings have len 768 (today 769) | Same, plus adapter raises on 767/769 |
| 3 | `test_thresholds`: monkeypatched `settings.THRESHOLD_SEM=0.70` changes the `AnalysisRunRequest()` default | Grep finds no literal 0.75/0.85 threshold defaults |
| 4 | `test_char_cnn_guard`: comment-padded trivial snippet gives `effective_length < 60`; `"//x"` inside a string literal is preserved | Weight-gated guard test returns `insufficient_length` |
| 5 | `test_benchmark_suite`: hand-computed AUC/F1/FPR; no problem appears in two splits; the stub run on the fixture emits the schema | CLI runs end to end on the fixture |

## Commit Slicing / Rollout / Rollback

1. `test: make pytest suite reproducible without manual setup` (D1-D3)
2. `fix(analysis): index and query 768-dim semantic vectors only` (D4-D6). Rollout: deploy, then `docker compose exec backend python reindex_chroma.py --mode slice`.
3. `refactor(config): single canonical semantic/AI thresholds` (D7)
4. `fix(char-cnn): count effective chars excluding comments in guard` (D8)
5. `feat(benchmark): add golden-set manifest builder and metric suite` (D9)

Rollback: revert each commit on its own. For unit 2 the legacy collection is still intact, so the revert alone restores the old behavior, and `codigos_referencia_v2` can be deleted. No SQL migration is involved.

## Open Questions

- [ ] Batch uses linear calibration (`baseline=0.75`, `batch_analysis_service.py:234`), while sync and async use the sigmoid. That is a separate false-positive source. It is out of scope here; recommended as a follow-up.
- [ ] Moving archetypes to 0.85 changes `benchmark_archetypes_results.json` for calibrated sims in [0.75, 0.85). Regenerating it needs weights.
