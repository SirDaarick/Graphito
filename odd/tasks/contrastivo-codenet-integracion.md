# Feature: Deploy the trained GraphCodeBERT adapter (B_s1) in the REAL engine

## Objective
Replace the zero-shot `v2_norm` secondary signal with `v2_norm` + the frozen F3/F4 headline adapter `ft_B_s1`
(user decision 2026-10-23, after the F4 results: equal or better on everything measured, never significantly
worse; see `contrastivo-codenet-f4.md`). The signal stays secondary and non-deciding (Channel A is still Jaccard).

## Scope / constraints
- The adapter ships in the verified deploy bundle: `models/deploy/gcb_adapter/{adapter_config.json,
  adapter_model.safetensors}` (2.4 MB), listed with sha256 in `manifest.json` under `files` and described in
  `gcb.adapter`. The other bundle files (Channel A/B calibrations, CharCNN checkpoint) must stay byte-identical.
- No new runtime dependency: the production image has `torch` and `transformers` only, so the LoRA merge is done
  with `W += (alpha / r) * B @ A` on the `query`/`value` weights (`models/graphcodebert/v2/lora_merge.py`) and is
  tested against `peft`'s `merge_and_unload`.
- The zero-shot facade `GraphCodeBERTInference` keeps refusing adapters (`tests/test_lora_guard.py`); the adapter
  path is a separate class.
- The engine fingerprint (Chroma collection name) must change when an adapter is used and must stay unchanged
  (`gcb_v2_mean_5ae0c89a3576`) when it is not. Reindexing references is required (documented step).
- Fail closed as before: a manifest adapter with a wrong hash, missing file or unreadable weights raises
  `ArtifactError`/`InferenceError`, never a silent zero-shot fallback.
- UI/PDF/API labels must stop saying "zero-shot" when the adapter is active.
- Artifacts in English; UI copy in Spanish (project convention). Conventional commits, no attribution.

## Route
Inline (the Agent tool is restricted to explicit user requests): LoRA merge and adapter facade in `models/`,
loader + engine + settings in `backend/`, the bundle script, labels in `frontend/` and `pdf_service`.

## Tasks
- [x] T1 `lora_merge.py` + tests (equal to peft's merge on a tiny model; error cases); `adapter.build_embedder` uses it
- [x] T2 `models/graphcodebert/v2/finetuned.py`: facade-compatible `predict_code` with the merged adapter
- [x] T3 `scripts/add_gcb_adapter_to_deploy.py` + tests; run it on `models/deploy/`
- [x] T4 Loader: `ArtifactBundle` adapter fields, verification (backend tests first)
- [x] T5 Engine: factory selection, fingerprint, `model_versions`, `GCB_ADAPTER_ENABLED` setting (tests first)
- [x] T6 Labels (API/PDF/UI), README rollout and reindex step, project docs
- [x] T7 Full backend + ML verification; commit. Frontend checks NOT run (no `node_modules` in the worktree); the
  only frontend change is one label constant and two comments, covered by `backend/tests/test_frontend_contract.py`
- [ ] T8 Reindex the references in the deployment (operator step, see `models/deploy/README.md`)

## Evidence
- Merge: `tests/test_lora_merge.py` (9) compares with `peft.merge_and_unload` on a tiny RoBERTa, atol 1e-6; the real
  B_s1 adapter merged this way reproduces the training-path embeddings (cosine > 0.9999, `tests/test_v2_adapter.py`).
- Bundle: `models/deploy/manifest.json` diff is purely additive (16 insertions, 1 comma); Channel A/B calibrations
  and the CharCNN checkpoint hashes are unchanged. Adapter identity `b5842ab13eaa2718...` = the one frozen in
  `f4_frozen.json`.
- Backend: loader (9 tests, does not import torch), engine (9 tests), existing suites adjusted only where the old
  policy said "no adapter in the REAL engine" (`test_inference_engines.py`) or asserted the old label
  (`test_frontend_contract.py`). Backend 332 passed; root `tests/` 1196 passed, 1 skipped.
- End to end with the real factories over `models/deploy` (scratch script): collection with the adapter
  `gcb_v2_mean_f540d15ff74f`; with `GCB_ADAPTER_ENABLED=false` `gcb_v2_mean_5ae0c89a3576` (unchanged, the v2_norm
  one). Cosine between two unrelated programs: 0.34 with the adapter, 0.87 without; cosine between the adapter
  and zero-shot vector of the same program: 0.48.
- Decisions: neutral label "Normalización de identificadores · exploratorio, no decide" (true with or without the
  adapter); `model_versions` carries `gcb_adapter`/`gcb_adapter_sha256` only when the adapter is used, so older
  reports keep their shape; an embedding without `adapter_loaded` is refused when an adapter is expected.
