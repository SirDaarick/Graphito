# Golden set

Manifest builder for the false-positive benchmark (`scripts/benchmark_suite.py`).

## Corpus layout

The corpus location is always a CLI argument (nothing is hardcoded):

```
<root>/<problem_id>/{reference,original,copy,ai}/*.c|*.cpp
```

| class       | role       | label_copy | label_ai |
|-------------|------------|------------|----------|
| `reference` | reference  | false      | false    |
| `original`  | submission | false      | false    |
| `copy`      | submission | true       | false    |
| `ai`        | submission | false      | true     |

## Build a manifest

```bash
python data/golden_set/build_manifest.py <root> --seed 42 --test-ratio 0.3 --out data/golden_set/manifest.json
```

- The dev/test split is by `problem_id` (`sha256(seed:problem_id)` against `--test-ratio`); a problem never spans two splits (asserted).
- Files with identical content (`sha256`) are deduplicated; the first path in sorted order is kept.
- Counts per label, split and problem are printed; a warning is emitted for problems with fewer than 6 LLM files.
- `--synthetic` marks the manifest as synthetic data (propagated to the benchmark output).

## Run the benchmark

```bash
python scripts/benchmark_suite.py --manifest data/golden_set/manifest.json --engine stub --out benchmark_suite_results.json
```

`--engine stub` is only a smoke test of the pipeline. Results on the fixture in `tests/fixtures/golden_set_tiny/` are NOT evidence about the real models.
