# Run report: graphcodebert on test

## Provenance

| Field | Value |
|---|---|
| Run | graphcodebert/20261011-082155 |
| Split | test |
| Mode | zero_shot |
| Seed | 42 |
| Manifest | data/splits/split_v1.json.gz |
| Manifest sha256 | e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f |
| Calibration sha256 | null |
| Threshold source | null |
| Git | 69a19d8a3ede60fce5247fe807e98c31657a076e (dirty: False) |
| Created (UTC) | 2026-10-11T08:21:55.689054+00:00 |

## Threshold-free metrics (observed view)

| Metric | Value | CI95 | n | n_pos | n_neg | Note |
|---|---|---|---|---|---|---|
| roc_auc | 0.9437 | [0.9302, 0.9620] | 1908545 | 338 | 1908207 |  |
| pr_auc | 0.0019 | [0.0008, 0.0048] | 1908545 | 338 | 1908207 |  |
| ece | 0.2002 | [0.1757, 0.2411] | 1908545 | 338 | 1908207 |  |
| map_at_r | 0.3846 | [0.1998, 0.5481] |  |  |  |  |

## Operating points

| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |
|---|---|---|---|---|---|---|---|---|---|
| fpr_0.05 | 0.6223 | val_raw_score | 0.0500 | observed | 0.0029 [0.0009, 0.0076] | 0.6065 [0.4444, 0.7095] | 0.0366 [0.0196, 0.0504] | 0.0058 [0.0019, 0.0150] | ok |
| fpr_0.05 | 0.6223 | val_raw_score | 0.0500 | balanced | 0.9431 [0.9127, 0.9685] | 0.6065 [0.4444, 0.7095] | 0.0366 [0.0196, 0.0504] | 0.7383 [0.5992, 0.8124] | ok |
| fpr_0.01 | null | val_raw_score | 0.0100 | - | - | - | - | - | ok; no_threshold_meets_target |

## Plots

- ![roc.png](roc.png)
- ![pr.png](pr.png)
- confusion.png not produced: omitted (counts are in metrics.json operating_points)
- reliability.png not produced: scores_not_probabilities

## Warnings

- unachievable: operating point fpr_0.01 has no threshold (no_threshold_meets_target)

## Limitations

- Student overlap: the split unit is the block (course letter + Zx), not the student, so the same student can appear in train, val and test. Per-student style can leak across splits; treat results as optimistic for unseen students.
