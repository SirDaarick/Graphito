# GraphCodeBERT zero-shot evaluation

- Run: graphcodebert/20261011-082155; manifest sha256 e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f
- Model revision: 2b0488a7bb0eefc7041f1bb2cad1ab26b0da269d; seed 42; n_boot 1000; limit_assignments None
- Split: test, evaluated once. Pooling and thresholds were chosen on val only (raw scores).

## Test, view `all`

| Method | Pooling | PR-AUC [CI95] | MAP@R [CI95] | ROC-AUC [CI95] | n | n_pos |
|---|---|---|---|---|---|---|
| v2 | mean | 0.0015 [0.0003, 0.0051] | 0.2946 [0.1448, 0.4129] | 0.8559 [0.7960, 0.8925] | 1908545 | 338 |
| v2_nodfg | mean | 0.0009 [0.0003, 0.0025] | 0.2906 [0.1446, 0.4119] | 0.8513 [0.7876, 0.8892] | 1908545 | 338 |
| jaccard | - | 0.0019 [0.0008, 0.0048] | 0.3736 [0.1954, 0.5326] | 0.9446 [0.9296, 0.9641] | 1908545 | 338 |
| winnowing | - | 0.0019 [0.0008, 0.0048] | 0.3846 [0.1998, 0.5481] | 0.9437 [0.9302, 0.9620] | 1908545 | 338 |
| legacy | cls | 0.0004 [0.0002, 0.0010] | 0.1676 [0.0751, 0.2501] | 0.7405 [0.6527, 0.7997] | 1908545 | 338 |

## Test, view `no_identical`

| Method | Pooling | PR-AUC [CI95] | MAP@R [CI95] | ROC-AUC [CI95] | n | n_pos |
|---|---|---|---|---|---|---|
| v2 | mean | 0.1277 [0.0433, 0.2174] | 0.4324 [0.3192, 0.5463] | 0.8834 [0.8218, 0.9172] | 1846058 | 338 |
| v2_nodfg | mean | 0.1297 [0.0426, 0.2192] | 0.4360 [0.3286, 0.5538] | 0.8794 [0.8167, 0.9153] | 1846058 | 338 |
| jaccard | - | 0.0466 [0.0212, 0.3029] | 0.5492 [0.4162, 0.6862] | 0.9747 [0.9667, 0.9832] | 1846058 | 338 |
| winnowing | - | 0.0437 [0.0205, 0.2686] | 0.5569 [0.4206, 0.6941] | 0.9738 [0.9659, 0.9820] | 1846058 | 338 |
| legacy | cls | 0.0371 [0.0177, 0.0760] | 0.2561 [0.1646, 0.3403] | 0.7649 [0.6660, 0.8299] | 1846058 | 338 |

## Data

- val: 5089 files, 9 assignments, 1595275 pairs (174 positive); `no_identical` drops 49342; exclusions {'ambiguous_files': 49, 'unlabeled_files': 1670, 'ambiguous_pairs': 32412, 'unlabeled_pairs': 322592}; same-student candidate pairs 0
- test: 6797 files, 14 assignments, 1908545 pairs (338 positive); `no_identical` drops 62487; exclusions {'ambiguous_files': 147, 'unlabeled_files': 2374, 'ambiguous_pairs': 71360, 'unlabeled_pairs': 499691}; same-student candidate pairs 0
- v2 (dfg): 11886 file embeddings, 0 failed (scored 0), parse-error rate 0.25096752481911494, truncation rate 0.11198048123843177, mean windows 4.680548544506141, cache {'hits': 5708, 'misses': 6178}
- v2_nodfg (nodfg): 11886 file embeddings, 0 failed (scored 0), parse-error rate 0.25096752481911494, truncation rate 0.035756352010768974, mean windows 4.680548544506141, cache {'hits': 5708, 'misses': 6178}
- legacy (legacy_adapter): 11886 file embeddings, 0 failed (scored 0), parse-error rate None, truncation rate None, mean windows 4.257193336698637, cache {'hits': 5708, 'misses': 6178}

## Caveats

- `legacy` is the frozen pre-v2 pipeline with its adapter (or base encoder, see reason); its numbers are not comparable with earlier reports.
- Ground-truth labels are noisy (plagiarism clusters annotated per assignment); unlabeled and ambiguous files are excluded.
- Curves are thinned to at most 2000 points and gzip-compressed; AUC values use every pair.
- `calibration.json` (isotonic on val cosine) is for SDD-4; no metric here uses it.
