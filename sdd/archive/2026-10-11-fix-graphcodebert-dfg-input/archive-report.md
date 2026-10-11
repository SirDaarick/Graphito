# Archive Report: fix-graphcodebert-dfg-input

**Archived**: 2026-10-11
**Verdict at archive**: PASS WITH WARNINGS (see `verify-report.md`; 0 critical; documented deviations GE1.2, GE1.3, GE3.3, GE7.4, GE7.5, GV2.1; NF5 partial)

## Main spec

- `sdd/specs/fix-graphcodebert-dfg-input.md`: final spec with amendments (windows 382/191/max 16, `dfg_nodes_used` = distinct nodes placed, facade default `input_version="legacy"` with adapter off until SDD-4).

## Archived artifacts

`sdd/archive/2026-10-11-fix-graphcodebert-dfg-input/`: `proposal.md`, `spec.md`, `design.md`, `tasks.md`, `verify-report.md`, `archive-report.md`.

## Engram traceability

| Artifact | Topic key | Observation ID |
|---|---|---|
| Explore | `sdd/fix-graphcodebert-dfg-input/explore` | 210 |
| Proposal | `sdd/fix-graphcodebert-dfg-input/proposal` | 211 |
| Spec + design | `sdd/fix-graphcodebert-dfg-input/spec-design` | 212 |
| Tasks | `sdd/fix-graphcodebert-dfg-input/tasks` | 213 |

## Delivered

- `models/graphcodebert/v2/`: C/C++ DFG walker with golden parity against the vendored upstream walker, upstream-faithful input features and attention mask, eager forward with a 4D additive mask (verified honoured on transformers 5.14), sliding windows over the full-file DFG, CLS/mean pooling, embedding cache, per-assignment pair scoring, lexical baselines, zero-shot evaluation CLI.
- `models/graphcodebert/inference.py` facade (default legacy, adapter never loaded) and `legacy_inference.py` (frozen path; adapter only via `load_adapter=True` for the labelled baseline).
- Vendored reference `tests/reference/graphcodebert/` (microsoft/CodeBERT `c0de43d`, MIT).
- Real run `runs/graphcodebert/20261011-082155/` (n_boot 1000): lexical baselines beat zero-shot v2 on ROC-AUC/MAP@R; DFG adds no measurable gain; v2 clearly beats the legacy pipeline.
- Branch chain (not pushed): `feat/fix-graphcodebert-dfg-input` <- `feat/fix-gcb-01-dfg` <- `-02-encode` <- `-03-windows` <- `-04-eval` <- `-05-run`.

## Carried forward

- Deferred follow-ups in `tasks.md` (runtime embedding failures cached as permanent; legacy cache key adapter digest; legacy `truncated=False` negative test).
- Gentle AI defect: `review start` returned `candidate_context_unavailable` for slice 2; replaced by an independent verifier (PASS WITH FINDINGS, fixed in 55a34e3). Draft issue text given to the user.
- SDD-4: choose the operational Channel A score (v2 zero-shot vs lexical), switch the facade default and reindex Chroma, recalibrate thresholds.
- Phase 2: contrastive fine-tuning on plagiarism clusters.
