# models/deploy

Deploy artifacts the backend loads in `INFERENCE_MODE=REAL`. They are mounted read-only in the
container through the existing `./models:/models:ro` volume. The only writer of this directory is
`scripts/build_deploy_artifacts.py`. Do not edit these files by hand: the backend verifies every
sha256 at startup and refuses to score when one differs.

> Label: these artifacts are **not validated against reference-derived plagiarism**. The
> Channel A calibration was fitted on student-to-student pairs of split_v1 val. It was never
> fitted on copies derived from a teacher's reference solution.

## Contents

| Path | What | Source |
|------|------|--------|
| `manifest.json` | `graphito.deploy-manifest/v1`: the sha256 of every file, source run ids, threshold keys and values, raw-space reference thresholds, git sha and package versions | build script |
| `channel_a/calibration.json` | Isotonic `graphito.calibration/v1` calibration of the 5-token shingle Jaccard, fitted on val only. The backend uses the threshold key `fpr_0.05` | fitted from the split_v1 val plagiarism pairs |
| `channel_b/best.pth` | CharCNN v2 checkpoint (a verbatim copy) | `runs/char_cnn/<run>/best.pth` |
| `channel_b/calibration.json` | CharCNN Platt calibration (a verbatim copy). The backend uses the threshold key `fpr_0.01` | `runs/char_cnn/<run>/calibration.json` |

`channel_b/best.pth` is tracked through one exact `.gitignore` exception. Every other `*.pth` stays
ignored. The legacy `models/char_cnn/best_model.pth` is never read or written by the build.

## Provenance

- Channel A scores are computed the same way the SDD-3 GraphCodeBERT evaluation computes its
  `jaccard` baseline. The val pairs come from `EvalPairs.from_manifest(manifest, "val")`, which
  excludes ambiguous pairs. Each file is reduced to `jaccard_set` (5-token shingles of the
  abstracted token stream), and pairs are scored per assignment block with `SetSimilarity`.
  The calibration is `build_calibration(method="isotonic", targets=(0.05, 0.01))` from
  `models.evaluation`, which itself is unchanged.
- `channel_a.raw_val_threshold_ref` is the raw val threshold from the GraphCodeBERT run's
  `thresholds_val.json`, and `channel_a.raw_threshold_equivalent` is the lowest raw val score
  that the calibrated threshold flags. Both are recorded for cross-checking only. Decisions use
  the calibrated threshold.
- The build refuses (exit 1, nothing written) in these cases:
  - the split manifest sha256 differs between the split file, the CharCNN calibration and the
    GraphCodeBERT run;
  - a run file's sha256 differs from its run `config.json`;
  - the val pairs differ from the GraphCodeBERT run's `selection.json`;
  - `fpr_0.05` is unachievable for Channel A, or `fpr_0.01` is missing for Channel B.

## Rebuild

Run from the repository root. Scoring the full val set (about 1.6M pairs) takes a while, so run it
detached:

```bash
python scripts/build_deploy_artifacts.py \
    --charcnn-run runs/char_cnn/20261011-015734 \
    --gcb-run runs/graphcodebert/20261011-082155
```

- `--dry-run` runs every check and prints the manifest without writing anything.
- `--force` overwrites existing files whose bytes differ. Without it, the build refuses.
- `--limit-assignments N` is for debugging: it scores only the first N val assignments. It is
  refused for the default output directory unless `--dry-run` is also given.
- Each file is written atomically, and `manifest.json` is written last.

After a rebuild, commit the changed files together with `manifest.json`.
