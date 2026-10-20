# Feature: Contrastive CodeNet training, phase F0 (data preparation)

## Objective
Implement F0 of `Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md`: build a
reproducible, leak-free manifest and a cached `v2` input set from Project CodeNet C++1000 for the later
contrastive LoRA training of the Channel A encoder. Training and evaluation are out of scope (F1+).

## Scope / constraints
- Raw data (outside the repo, never committed): `C:\Users\edani\datasets\codenet\`
  - Accepted: `cpp1000\Project_CodeNet_C++1000\<problem>\*.cpp` (500 per problem, 1000 problems)
  - Wrong Answer: `wa\Project_CodeNet\data\<problem>\C++\*.cpp` (15 per problem, `code_size` <= 4000)
  - Status metadata: `Project_CodeNet\metadata\<problem>.csv`
- Base input is `v2_norm` (user request 2026-10-20, backed by `runs/robustness_v2norm/20261019-222018` and
  `odd/tasks/gcb-v2-norm.md`): code is canonicalized with `models.logic_eval.canonical.canonicalize_code`
  before DFG/tokenization, the single-window fit is judged on the canonical code, and a canonicalizer
  failure falls back to raw code (counted in `stats.json`). Dedup shingles use the raw code (already
  identifier-abstracted). The first full run on raw code was stopped and discarded.
- Per problem keep up to 20 Accepted and 10 Wrong Answer that fit ONE `v2` window (no code or DFG
  truncation with `code_length=384`, `data_flow_length=128`).
- Drop Wrong Answer with token-shingle Jaccard > 0.9 against any kept Accepted of the same problem.
- Drop any sample with Jaccard >= 0.8 against a `Programas_ESCOM` program (threshold chosen here;
  the guide does not fix it). The max similarity distribution is recorded in `stats.json`.
- Split 80/10/10 by problem with a fixed seed. Problems need >= 2 kept Accepted.
- Output dir `C:\Users\edani\datasets\codenet\f0\`: `manifest.jsonl`, `cache_<split>.pkl`, `stats.json`.
- Code under `scripts/`, tests under `tests/`. Artifacts in English. Conventional commits, no attribution.
- The working tree has unrelated uncommitted thesis changes: commit only this feature's files, by path.
- Planning heuristic ~400 changed lines per task (advisory).

## Route
Inline: the work is one script plus one test file, written from a bounded read of `v2/encode.py`,
`v2/embed.py`, `v2/baselines.py`. The Agent tool is restricted to explicit user requests here.

## Tasks
- [ ] T1 Pure helpers + tests (test-first): `split_problems`, `near_duplicate`, `fits_one_window`
- [ ] T2 `scripts/prepare_codenet_contrastive.py`: selection, dedup vs ESCOM, manifest, `v2` input cache
- [ ] T3 Run F0 on the full benchmark; record counts per stage in `stats.json` and below

## Evidence
(pending)
