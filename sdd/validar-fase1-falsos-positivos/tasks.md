# Tasks: validar-fase1-falsos-positivos

Legend: [W] = needs model weights or network (cannot be verified in this env; verify later). Commits are sequential (C1 first). Within a commit, tasks run in listed order unless marked (parallel). RED = write the test first and observe failure.

## C1. `test: make pytest suite reproducible without manual setup` (R1; D1-D3)

- [ ] T1.1 Baseline RED: run `pytest tests/ backend/tests/` from repo root and record collection errors (no files touched). Verify: command exits non-zero.
- [ ] T1.2 Create `pytest.ini` (`pythonpath = . backend`, `testpaths = tests backend/tests`, markers `requires_charcnn_weights`, `requires_graphcodebert`), `tests/conftest.py` (availability probes: `models/char_cnn/best_model.pth` exists; `AutoConfig.from_pretrained("microsoft/graphcodebert-base", local_files_only=True)` succeeds; auto-skip with reason), `requirements-dev.txt` (`-r backend/requirements.txt` + `scikit-learn`). (R1.1, R1.4)
- [ ] T1.3 RED then GREEN: add `backend/tests/test_auth_lazy_import.py` (blocks `google.oauth2` via `sys.modules` stub, asserts import of `auth_service` works and `login_with_google` raises 503-class error). Modify `backend/app/application/services/auth_service.py`: move `google.*` imports into `login_with_google`, map `ImportError` to HTTP 503. (R1.2, R1.3)
- [ ] T1.4 (parallel with T1.3) Modify `tests/test_char_cnn_robustness.py` (`pytest.importorskip("sklearn")`, weight marker), `tests/test_calibration_experiment.py` and `tests/test_escom_units.py` (markers), `tests/test_e2e_analysis.py` (move module-level `settings.*` mutation into `run_e2e_test`; weight marker). (R1.4)
- Verify: `pytest tests/ backend/tests/ -q` exits 0 (only pass or skip, 0 collection errors).
- Flags: tests marked weights are skipped here; they are not verified.

## C2. `fix(analysis): index and query 768-dim semantic vectors only` (R2; D4-D6)

- [ ] T2.1 RED: create `backend/tests/test_vector_dims.py` and modify `backend/tests/conftest.py` (`InMemoryVectorStore` records last embedding, asserts len 768). Cases: reference upsert via `problem_service` is len 768; `/analysis/run` without `referencia_id` queries len 768; same code with different `ai_prob` gives identical similarity (R2.5); adapter raises `ValueError` on 767 and 769. Observe failure (today 769).
- [ ] T2.2 GREEN: modify `backend/app/application/orchestrator/analysis_orchestrator.py` (sync and async paths, ~:99,125,308,328: drop `hybrid_vector`), `backend/app/application/services/batch_analysis_service.py` (~:219-223), `backend/app/application/services/problem_service.py` (:71 index the semantic vector). (R2.1, R2.3)
- [ ] T2.3 GREEN: modify `backend/app/infrastructure/vector_store/chroma_adapter.py`: collection `codigos_referencia_v2` (`hnsw:space=cosine`, `embedding_dim=768`), `len==768` check in `upsert` and `query` raising `ValueError`, startup warning if legacy non-empty and v2 empty. Modify `backend/app/domain/ports/inference_port.py` docstring: `generate_hybrid_embedding` deprecated, not for indexing. (R2.2, R2.3)
- [ ] T2.4 Create `backend/reindex_chroma.py` (`--mode slice` default copies legacy `[:768]`; `--mode reembed` from Postgres `REFERENCIA` via `get_inference_engine()`; idempotent upsert; opt-in `--drop-legacy`). Add a small test for the slice logic against an in-memory/temp store if feasible without a Chroma server. (R2.4)
- [ ] T2.5 Docs: add migration note to `README.md` (769-dim legacy vectors, new v2 collection, steps: deploy, `docker compose exec backend python reindex_chroma.py --mode slice`, rollback by revert and deleting v2). (R2.4)
- Verify: `pytest backend/tests/test_vector_dims.py -v`, then `pytest tests/ backend/tests/ -q`.
- Flags: `--mode reembed` and the real Chroma path need [W] and a running Chroma/Postgres; the unit tests use the in-memory store.

## C3. `refactor(config): single canonical semantic/AI thresholds` (R3; D7)

- [ ] T3.1 RED: create `backend/tests/test_thresholds.py` (monkeypatch `settings.THRESHOLD_SEM=0.70` changes `AnalysisRunRequest()` default; no env override gives 0.85; stub engine requires thresholds keyword-only). Observe failure.
- [ ] T3.2 GREEN: modify `backend/app/config.py` (`THRESHOLD_SEM=0.85`, `THRESHOLD_AI=0.70`; spec names these `THRESHOLD_SEM_DEFAULT`/`THRESHOLD_AI_DEFAULT`, so alias or use the spec names and keep one source), `backend/app/domain/ports/inference_port.py`, `backend/app/infrastructure/inference/stub_engine.py`, `backend/app/infrastructure/inference/real_engine.py` (thresholds keyword-only, no defaults), `backend/app/presentation/schemas/analysis.py` (`Field(default_factory=lambda: settings.THRESHOLD_SEM)`), callers in orchestrator and `batch_analysis_service.py` pass `settings.*`. Domain must not import config.
- [ ] T3.3 Modify `tests/test_calibration_experiment.py` (:147-157), `scripts/benchmark_student_archetypes.py` (:259), `tests/test_e2e_analysis.py`: use `settings.THRESHOLD_SEM` or a named, commented 0.75 override. Document `baseline=0.85` in `calibrate_semantic_similarity` as distinct (comment only, R3.5).
- [ ] T3.4 Docs: `README.md` section on thresholds and env override (`THRESHOLD_SEM`).
- Verify: `pytest tests/ backend/tests/ -q`; `rg "0\.85|0\.75" backend/app scripts tests` shows no threshold-default literals.
- Flags: archetype benchmark regeneration (`benchmark_archetypes_results.json`) needs [W]; do not regenerate here (open question).

## C4. `fix(char-cnn): count effective chars excluding comments in guard` (R4; D8)

- [ ] T4.1 RED: create `tests/test_char_cnn_guard.py` (no torch): all-comment 500-char file has `effective_length < 60`; 40 chars code + 300 comment block fires; 80 chars code + trailing comment does not; `printf("// not a comment");` literal chars counted; `/* */` inside string preserved. Add a weight-gated test (`requires_charcnn_weights`) that `predict_text` returns `insufficient_length: True`, `ai_probability: 0.05` for a comment-only file. [W]
- [ ] T4.2 GREEN: modify `models/char_cnn/preprocess.py` (`CharPreprocessor.effective_length(text)` = non-whitespace length after `strip_c_comments`) and `models/char_cnn/inference.py` (:85 use it, named constant `MIN_NON_WS_CHARS = 60`; model input stays original text, R4.3). Ensure the helper is importable without torch (lazy torch import if needed). Do not edit weights.
- Verify: `pytest tests/test_char_cnn_guard.py -v` (pure tests pass; weight test skipped here [W]).

## C5. `feat(benchmark): add golden-set manifest builder and metric suite` (R5; D9)

- [ ] T5.1 Create fixture `tests/fixtures/golden_set_tiny/**` (3-4 problems, layout `<problem_id>/{reference,original,copy,ai}/*.c`, a few files each, plus one duplicate file for dedup).
- [ ] T5.2 RED: create `tests/test_benchmark_suite.py`: hand-computed AUC/F1/FPR on a toy array; single-class split gives AUC `None`; builder with seed 42 twice yields identical manifests; no `problem_id` in two splits; dedup by sha256; stub run on fixture emits schema with `synthetic: true`, `threshold_ai`, runs at 0.85 and 0.70 for A, B, fused. Observe failure (modules missing).
- [ ] T5.3 GREEN: create `data/golden_set/build_manifest.py` (corpus roots as CLI args, `--seed`, `--test-ratio`, split by `sha256(problem_id)` plus seed, assertion of no cross-split problem, dedup, counts per label/split/problem, warn if <6 LLM files per problem; fields per design manifest plus `sha256`) and `data/golden_set/README.md`.
- [ ] T5.4 GREEN: create `scripts/benchmark_suite.py` (`--manifest`, `--engine stub|real`, `--out`, `--threshold-ai`; numpy-only AUC/F1/FPR; reuses `calibrate_semantic_similarity` + `compute_decision`; stdout table; JSON output).
- Verify: `pytest tests/test_benchmark_suite.py -v`; then `python data/golden_set/build_manifest.py <fixture args>` and `python scripts/benchmark_suite.py --engine stub --manifest <out>` end to end.
- Flags: `--engine real` and any real-corpus run need [W] and the corpus; not verifiable here. Fixture results are not evidence about real models (R5.7).

## Out of scope / open questions
- Batch path uses linear calibration with `baseline=0.75` (`backend/app/application/services/batch_analysis_service.py:234`) while sync/async use sigmoid. Separate false-positive source; recommended follow-up only, not changed here.
- Regenerating `benchmark_archetypes_results.json` after the 0.85 move needs weights.
- Real-corpus benchmark and `pad=True/False` experiment wait for the corpus.

## Apply progress (sdd-apply)

IMPORTANT: this apply run had NO command-execution tool (only Read/Edit/Write/Glob/Grep), so NO test or command was run. All code below is written but UNVERIFIED; for that reason no checkbox above is ticked and no RED/GREEN was observed. Run the Verify command of each group before ticking.

Decision: setting names are `THRESHOLD_SEM` / `THRESHOLD_AI` (design names); the spec names `THRESHOLD_SEM_DEFAULT` / `THRESHOLD_AI_DEFAULT` were not used. No commits were made (user's working tree has unrelated edits).

### C1 (implemented, unverified)
Files: `pytest.ini`, `requirements-dev.txt`, `tests/conftest.py`, `backend/app/application/services/auth_service.py`, `backend/tests/test_auth_lazy_import.py`, `tests/test_char_cnn_robustness.py`, `tests/test_calibration_experiment.py`, `tests/test_escom_units.py`, `tests/test_e2e_analysis.py`.
Proposed commit: `test: make pytest suite reproducible without manual setup`

### C2 (implemented, unverified)
Files: `backend/tests/conftest.py`, `backend/tests/test_vector_dims.py`, `backend/tests/test_reindex_slice.py`, `backend/app/application/orchestrator/analysis_orchestrator.py`, `backend/app/application/services/batch_analysis_service.py`, `backend/app/application/services/problem_service.py`, `backend/app/infrastructure/vector_store/chroma_adapter.py`, `backend/app/domain/ports/inference_port.py`, `backend/reindex_chroma.py`, `tests/test_e2e_analysis.py`, `README.md`.
Proposed commit: `fix(analysis): index and query 768-dim semantic vectors only`

### C3 (implemented, unverified)
Files: `backend/tests/test_thresholds.py`, `backend/app/config.py`, `backend/app/domain/ports/inference_port.py`, `backend/app/infrastructure/inference/stub_engine.py`, `backend/app/infrastructure/inference/real_engine.py`, `backend/app/presentation/schemas/analysis.py`, `backend/app/application/services/batch_analysis_service.py` (passes `settings.*`; linear calibration at baseline 0.75 untouched), `backend/app/application/orchestrator/analysis_orchestrator.py` (docstring note only), `tests/test_calibration_experiment.py`, `scripts/benchmark_student_archetypes.py`, `README.md`.
Proposed commit: `refactor(config): single canonical semantic/AI thresholds`
Pending check: `rg "0\.85|0\.75" backend/app scripts tests` (remaining hits expected: config default, sigmoid baseline, batch baseline 0.75, calibration assertions).

### C4 (implemented, unverified)
Files: `models/char_cnn/preprocess.py` (`MIN_NON_WS_CHARS`, `effective_length`), `models/char_cnn/inference.py`, `tests/test_char_cnn_guard.py`. Weight-gated test is [W].
Proposed commit: `fix(char-cnn): count effective chars excluding comments in guard`

### C5 (implemented, unverified)
Files: `tests/fixtures/golden_set_tiny/**` (4 problems, 1 duplicate), `tests/test_benchmark_suite.py`, `data/golden_set/build_manifest.py`, `data/golden_set/README.md`, `scripts/benchmark_suite.py`.
Proposed commit: `feat(benchmark): add golden-set manifest builder and metric suite`
Deviation: builder takes a single `<root>` (design D9 layout) instead of separate human/DeepSeek roots; `created_at` is added only by the CLI so `build_manifest()` is deterministic.

## Summary
5 commits, 18 tasks; commits are strictly sequential, T1.3 and T1.4 are parallel within C1. Tasks needing weights or services [W]: T2.4 (reembed mode), T3 archetype regeneration, T4.1 weight-gated test, T5.4 (`--engine real`).
