# Feature: gcb-v2-norm — deploy GraphCodeBERT with canonical identifier renaming

## Objective
Replace the deployed Channel A secondary embedding `v2` (GraphCodeBERT v2, DFG, mean pooling) with
`v2_norm`: the same model applied to code whose user-defined identifiers are canonically renamed
(`models/logic_eval/canonical.py`) before embedding, for both references and submissions.

## Why
`runs/robustness_v2norm/20261019-222018` (ROC-AUC, split_v1 test plagiarism pairs):
- T0: v2 0.856 → v2_norm 0.902 (+0.046 [0.017, 0.097]);
- T1 (identifier renaming): v2 0.684 → v2_norm 0.902; the renaming vulnerability is removed (Δ +0.171 [0.066, 0.306]).

E1 grouping (`runs/logic_eval/20261013-152644`): v2_norm ≈ v2 (no significant difference).

## Scope
- Backend: canonicalize before GraphCodeBERT embedding in the REAL engine, in one place shared by
  single, batch and reference indexing.
- The embedding fingerprint includes the canonicalization version, so the Chroma collection name changes
  and old vectors are never mixed with new ones.
- Reindex instructions (rollout) updated.
- The API, PDF and UI expose the method name honestly ("GraphCodeBERT con normalización de identificadores").

Out of scope: the Channel A decision (still lexical Jaccard), CharCNN, and the thesis text (separate task).

## Constraints
- Fail-closed behaviour is unchanged (503, never a stub fallback).
- STUB mode is unchanged.
- Canonicalization failure on unparsable code must not crash the request: fall back to raw code for that
  file, recorded in the report metadata, or follow the design the writer documents with a test.
- No changes to `models/deploy/` artifacts (GraphCodeBERT is loaded from the HF cache, not the bundle).

## Tasks
- [x] T1 Map the embedding path (real engine, ScoringService, reference indexing, reindex script, fingerprint/collection name).
- [x] T2 Tests first (RED): canonicalization is applied to both sides; the fingerprint/collection name changes; single equals batch; reindex uses the same path; STUB is unchanged; an unparsable-code edge case.
- [x] T3 Implement (GREEN) and refactor.
- [x] T4 Update the rollout docs (`models/deploy/README.md`) and the API/PDF/UI method label.
- [x] T5 Full backend and ML suites plus frontend checks.

## Route
Delegated direct (one writer): 2+ non-trivial files.

## Acceptance
All tests green; the collection name differs from `gcb_v2_mean_359032419bac`; a documented reindex step.

## Progress
- T1: path = `RealBimodalInferenceEngine.extract_semantic_embedding` (real_engine.py) is the only caller-facing embedder; ScoringService._gcb (single/async/batch), problem_service.add_reference_code and scripts/reindex_references.py all call it. Collection `gcb_{input_version}_{pooling}_{fp[:12]}` via chroma_adapter.collection_name_for_engine. Method label: pdf_service, `GCB_LABEL` in frontend/src/lib/dictamen.ts. Route: delegated direct.
- T2 RED: `backend/tests/test_gcb_canonicalization.py` failed at collection (ImportError: GCB_OK_RAW / CANONICALIZATION_VERSION missing).
- T3 GREEN: canonicalization inside the engine (`_canonical_predict`, executor thread); engine fingerprint = `pipeline_fingerprint(manifest_fp, "identifiers_v1")` (manifest fingerprint is still verified on the base fields, so `models/deploy/` is untouched); `model_versions` gains `gcb_canonicalization`. New collection: `gcb_v2_mean_5ae0c89a3576` (was `gcb_v2_mean_359032419bac`). Policy: canonicalizer is skipped inside ERROR nodes by itself; if it raises, raw code is embedded, `CANONICALIZATION_FALLBACK` context flag is set and `gcb_estado` becomes `OK_SIN_NORM`.
- T4: README rollout step 4, PDF label, `GCB_LABEL`, frontend contract test updated.
- T5: backend/tests 311 passed; tests/ + backend/tests/ 1470 passed, 1 skipped; frontend lint, typecheck, vitest (58), build all exit 0.
- Commits: see `git log feat/gcb-v2-norm`.
