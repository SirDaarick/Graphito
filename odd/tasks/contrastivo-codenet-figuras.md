# Feature: Figures and tables of the CodeNet experiment for the thesis

## Objective
Give the thesis author the evidence of F0-F4 as figures and tables, texts in Spanish, one file per figure, plus the
CodeNet dataset figures (user request 2026-10-23).

## Scope / constraints
- Every number comes from run artifacts (`runs/contrastivo_codenet/`, copied from `C:\Users\edani\datasets\codenet`,
  force-added like the other tracked runs) or from `derived/` (computed once by `derive_codenet_figure_data.py`).
- Output: `Documentacion/Documento/figuras/*.png` (300 dpi, serif, same style as `generate_tt_figures.py`) and
  `Documentacion/Documento/tablas/*.tex` (`table[H]`, `\hline` like the existing chapters).
- Guide for the author: `Documentacion/guias_implementacion/figuras_tesis_codenet.md` (captions, placement, caveats).

## Tasks
- [x] T1 Copy the small evidence files into the repo (1.1 MB)
- [x] T2 `scripts/derive_codenet_figure_data.py`: splits, program lengths, cosine histograms, t-SNE (GPU, one time)
- [x] T3 `scripts/generate_codenet_figures.py`: 18 figures and 6 tables; every figure was opened and reviewed, and
  the overlapping labels, legends over data, a confusing schematic and a clipped axis label were fixed
- [ ] T4 Compile the thesis with the tables (no LaTeX on this machine) and place the figures in the chapters

## Findings while drawing
- Kept CodeNet programs have a median of 26 non-empty lines (p90 43); the ESCOM E1 sample has 104 (p90 300). The
  single-window filter makes the training data about four times shorter than the evaluation data.
- Cosine on CodeNet val: same problem 0.97 -> 0.75, different problems 0.96 -> 0.27 (zero-shot -> headline adapter).
