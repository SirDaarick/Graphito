# Spec: validar-fase1-falsos-positivos (approved subset)

Scope: items 1-5 approved by the user. The corpus is not yet available, so the benchmark MUST run on a synthetic fixture. Keywords follow RFC 2119.

## R1. Reproducible test run

Context: root `tests/` cannot import `app` because `backend/` is not on `sys.path` (only `backend/tests/conftest.py` adds it). `auth_service.py:6-7` imports `google.oauth2` at module level. `google-auth>=2.28.0` is already declared in `backend/requirements.txt:16` but is not installed in this env.

- R1.1 `pytest tests/ backend/tests/` run from the repo root MUST collect and run with no manual `PYTHONPATH` or install steps. Mechanism: a root `conftest.py` (or `pytest.ini` with `pythonpath = backend .`) that puts `backend/` and the repo root on `sys.path`.
- R1.2 Importing `app.application.services.auth_service` (and anything that imports it, such as the API app) MUST NOT fail when `google-auth` is absent. Decision: keep `google-auth` in requirements (it is already there, so no new dependency) and move the `google.*` imports inside `login_with_google`, so the failure only happens when Google login is actually used.
- R1.3 When `google-auth` is missing, `login_with_google` MUST raise a clear service-level error (HTTP 503 or equivalent), not an `ImportError` at import time.
- R1.4 Tests that need torch or real weights MUST be skipped with a reason (`importorskip` or a marker) when the dependency is absent, not error out at collection.

Scenarios
- Given a clean checkout without `google-auth` installed, When I run `pytest tests/ backend/tests/` from the root, Then there are 0 collection errors.
- Given `google-auth` is not installed, When `POST /api/v1/auth/google` is called, Then the response is a controlled error, not a 500 stack trace.

## R2. Chroma lookups use only the 768-dim semantic vector

Context: `analysis_orchestrator.py:99,125` and `:308,328` (batch path), `batch_analysis_service.py:219-223`, and `problem_service.py:71` (`generate_hybrid_embedding`, 769-dim) store or query `semantic + [ai_prob]`. The `referencia_id` branch (`:109-121`) uses 768 dims. Appending `ai_prob` mixes the stylometry channel into the semantic similarity.

- R2.1 Every vector written to or queried from the vector store MUST be the 768-dim semantic embedding. No `ai_prob` component may be appended.
- R2.2 `VectorStorePort` implementations SHOULD reject (or log and reject) embeddings whose dimension is not 768.
- R2.3 The `generate_hybrid_embedding` port method MUST NOT be used for storage. It MAY remain as deprecated, or be removed together with its stub and real implementations.
- R2.4 A migration note (`docs` or the README) MUST state that existing stored vectors have 769 dims and that the Chroma collections need to be rebuilt by re-embedding the reference sources. It MUST give the steps. A re-index script is OPTIONAL. This change does not touch `backend/chroma_data/`.
- R2.5 The semantic similarity used for the same pair of codes MUST be equal between the `referencia_id` branch and the nearest-neighbour branch, up to the Chroma metric.

Scenarios
- Given a reference registered through `problem_service`, When its embedding is stored, Then the stored vector has length 768.
- Given a submission analyzed without `referencia_id`, When `query_nearest` is called, Then the embedding has length 768 and does not depend on `ai_prob`.
- Given two submissions with the same code but different `ai_prob`, When both are queried, Then the similarities are identical.

## R3. One canonical `threshold_sem`

Context: the default is 0.85 in `schemas/analysis.py:15`, `stub_engine.py:50`, `real_engine.py:95` and `inference_port.py:28`. The tests and the benchmark use 0.75 (`tests/test_calibration_experiment.py:147-157`, `scripts/benchmark_student_archetypes.py:259`).

- R3.1 `backend/app/config.py` MUST define `THRESHOLD_SEM_DEFAULT` (and SHOULD define `THRESHOLD_AI_DEFAULT`) as the single source. The default value is 0.85, which keeps the current API behavior.
- R3.2 The schema default, the port and the engines MUST read that setting. No other numeric literal 0.85 may stay as a threshold default.
- R3.3 The tests and scripts that use 0.75 MUST either read the same setting or declare the 0.75 as an explicit named override with a comment. The benchmark suite MUST report both 0.85 and 0.70 (R5.2).
- R3.4 The README or docs MUST document the value and how to override it (env var). A request may still override it per call.
- R3.5 The `baseline=0.85` in `calibrate_semantic_similarity` is a separate calibration parameter. It MUST be documented as distinct from the decision threshold and is not changed by this item.

Scenarios
- Given `THRESHOLD_SEM_DEFAULT=0.80` in the env, When a request omits `threshold_sem`, Then 0.80 is used.
- Given no env override, When a request omits `threshold_sem`, Then 0.85 is used in the API, the stub and the real engine.

## R4. CharCNN length guard counts non-whitespace characters after stripping comments

Context: `models/char_cnn/inference.py:85` computes `len("".join(text.split()))`, so a file made of comments passes the 60-character guard. The existing threshold of 60 stays.

- R4.1 `predict_text` MUST remove C/C++ comments (`//...` and `/* ... */`) before counting. It MUST NOT strip comment markers inside string or char literals.
- R4.2 The guard MUST count the remaining non-whitespace characters and keep the 60 threshold (named constant `MIN_NON_WS_CHARS`).
- R4.3 Stripping is used for the count only. The text sent to the model MUST remain the original text.
- R4.4 The guard SHOULD be a pure helper function that can be tested without loading torch.

Scenarios
- Given a 500-character file that is all comments, When `predict_text` runs, Then it returns `insufficient_length: True` and `ai_probability: 0.05`.
- Given a 40-character program plus a 300-character comment block, Then the guard fires.
- Given 80 characters of code with a trailing comment, Then the guard does not fire and the model runs.
- Given `printf("// not a comment");` counted as code, Then the string literal characters are counted.

## R5. Benchmark skeleton and golden-set manifest

- R5.1 `scripts/benchmark_suite.py` MUST compute AUC, F1 and FPR for channel A (semantic), channel B (stylometry) and the fused result. It reads a manifest plus a score source (stub or real engine through the `INFERENCE_MODE` mechanism).
- R5.2 The fused metrics MUST be computed at `threshold_sem` 0.85 and 0.70. `threshold_ai` MUST be explicit in the output. Output: JSON, plus a short table on stdout.
- R5.3 `data/golden_set/` MUST contain a manifest builder (a script) that takes a root directory of human files and a root of DeepSeek files and writes a manifest (JSONL or CSV) with `path`, `label` (human or llm), `problem_id`, `split` and a content `sha256`. The corpus location MUST be a CLI argument, not hardcoded.
- R5.4 The split MUST be by `problem_id` (all files of a problem go to the same split) and MUST be deterministic given a seed. The builder MUST assert that no problem appears in two splits.
- R5.5 The builder MUST deduplicate by content hash and report the counts per label, split and problem. It SHOULD warn if there are fewer than 6 LLM files per problem.
- R5.6 A tiny synthetic fixture (a few problems, a few C files per label) MUST be included so that the builder and the suite run end to end now, with the stub engine and no network. A test MUST cover the no-leakage property and the metric computation, including the degenerate case of a single class (AUC reported as null, not a crash).
- R5.7 The synthetic fixture results are NOT evidence about the real models. The output SHOULD carry a `synthetic: true` flag.

Scenarios
- Given the synthetic fixture, When I run the builder with seed 42 twice, Then both manifests are identical.
- Given the manifest, Then no `problem_id` appears in more than one split.
- Given the fixture and the stub engine, When I run `benchmark_suite.py`, Then it writes metrics for A, B and fused at both thresholds.
- Given a split that has only one class, Then AUC is null and the run finishes.

## Non-goals
- Halstead/McCabe features, `fusion_v2`, clang-format robustness.
- CharCNN retraining and the `pad=True` vs `pad=False` experiment (needs the corpus).
- Any change to model weights, or to `backend/chroma_data/` and `models/*` files.
- Calling the real corpus: the real run waits until it arrives.
- Changing the calibration function or the severity levels.

## Assumptions and risks
- A1. `google-auth` is treated as a declared dependency that is only missing from this env, so a lazy import plus a clear error is the chosen path. The alternative (only installing it) would keep the import-time coupling.
- A2. R2 breaks compatibility with existing vector stores: stored 769-dim vectors fail or return wrong results until re-indexed. The migration note is the mitigation.
- A3. The default stays at 0.85. If the thesis experiments need 0.75 as the default, that is a decision for the user, and the single setting makes it a one-line change.
- A4. The stripping in R4 is a lightweight lexer, not a full parser (no preprocessor handling).
