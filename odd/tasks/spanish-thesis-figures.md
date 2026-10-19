# Feature: Spanish labels for Chapter 8 thesis figures

## Objective
Regenerate g1-g5 (logic eval) and CharCNN v2 ROC/PR figures with Spanish labels,
from the existing runs, without retraining or re-evaluating models.

## Scope / constraints
- Runs are the source of truth: `runs/logic_eval/20261013-152644`, `runs/char_cnn/20261011-015734`.
- Default (English) output must stay byte-identical; Spanish is opt-in via `lang="es"`.
- No commits (requested by parent session).

## Tasks
- [x] T1 `lang` option in `models/logic_eval/plots.py` (g1-g5) — inline
- [x] T2 `--only-figures` mode in `scripts/logic_grouping_eval.py` (rebuild from run + embedding cache, verify sample ids, E1 MAP@R and E2 AUC) — inline
- [x] T3 `lang` option + `replot_curves` in `models/evaluation/report.py`, CLI `scripts/replot_run_curves.py` — inline
- [x] T4 Regenerate EN (hash check vs. originals) and ES; copy ES to `Documentacion/Documento/figuras/`
- [x] T5 Visual inspection, related pytest, update `modelado.tex` captions

## Evidence
- EN replots byte-identical (MD5) to run PNGs: roc, pr, g1-g4; g5 identical after restoring the
  em dash that was mojibake (`â€”`) in the working-tree `plots.py` (checked with a G5-only rebuild).
- `--only-figures` reproduced stored E1 MAP@R and E2 per-assignment AUC (atol 1e-9) for all 5 methods; 0 cache misses.
- pytest (test_eval_report, test_logic_eval_*): 39 passed.
- No commits (parent session instruction).

## Follow-ups (pre-existing, not changed)
- G5 ranking uses Jaccard (methods[0]) instead of v2 because of the selection condition in `main()`.
- G2 shows v2 and v2_nodfg (first two embedding methods), while the report text says v2 vs v2_norm.

## Route
Inline: changes are mechanical label maps plus one replot entry point per pipeline.
