# Channel A Robustness Evaluation Report: Structural Obfuscation

- **Run ID:** `None`
- **Split:** `test`
- **Manifest SHA256:** `e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f`
- **Seed:** `42`
- **Primary N_boot:** `1000`

## 1. Pre-Registered Hypotheses Verdicts

| Hypothesis | Statement | Contrast Statistic | Estimate [CI95] | Verdict |
|---|---|---|---|---|
| **H1** | Jaccard degrades more than v2 under T7@1.0 | `DiD(T7@1.0; jaccard, v2)` | 0.1284 [0.0142, 0.2764] | **REFUTED** (v2 drops more than jaccard) |
| **H2** | T1 acts as invariant control for Jaccard | `ΔROC-AUC_jaccard(T1)` | 0.0000 [-0.0000, 0.0000] | **FAILED** (nonzero drop 0.000002; implementation bug) |
| **H3** | DFG confers robustness under reordering T3 | `DiD(T3; v2_nodfg, v2)` | N/A | Not evaluated |

## 2. Transformation Validity & Edit Magnitude

| Condition | Applied Files | Applied Rate | Parse OK Rate | Mean Token Edit | Mean Abstract Edit |
|---|---|---|---|---|---|
| `T0` | 0/6797 | 0.0% | 100.0% | 0.0000 | 0.0000 |
| `T1` | 5826/6797 | 85.7% | 100.0% | 0.0000 | 0.0000 |
| `T5` | 6766/6797 | 99.5% | 100.0% | 0.0000 | 0.0000 |
| `T7@1.0` | 6766/6797 | 99.5% | 100.0% | 0.0000 | 0.0000 |

## 3. Method Performance by Condition (View: all)

| Condition | jaccard | v2 | v2_norm | DiD (jac - v2) |
|---|---|---|---|---|
| `T0` | 0.945 [0.930, 0.964] | 0.856 [0.796, 0.893] | 0.902 [0.863, 0.930] | — |
| `T1` | 0.945 [0.930, 0.964] | 0.684 [0.563, 0.775] | 0.902 [0.864, 0.928] | +0.172 [+0.065, +0.308] |
| `T5` | 0.950 [0.933, 0.964] | 0.768 [0.640, 0.852] | 0.794 [0.639, 0.879] | +0.093 [+0.020, +0.209] |
| `T7@1.0` | 0.931 [0.912, 0.949] | 0.714 [0.555, 0.814] | 0.708 [0.530, 0.823] | +0.128 [+0.014, +0.276] |

## 4. Figures

- [Degradation Curve](plots/degradation_curve.png)
- [Delta by Transform](plots/delta_by_transform.png)
- [Positive Drop Distribution](plots/positive_drop.png)
