## Baseline Comparison (Positives + Negatives)

| Method | Pos Class@1 | Pos Drug@1 | Neg PARP FP | Notes |
|--------|------------:|----------:|------------:|-------|
| Random | 50.0% | 37.5% | 75.0% | Random drug selection |
| Rule | 50.0% | 25.0% | 100.0% | IF DDR gene THEN PARP |
| S/P/E (cached) | 0.0% | 0.0% | 0.0% | cache_miss=100.0% |

## Full Benchmark (100 Cases)

| Metric | Value |
|--------|-------|
| Total Cases | 100 |
| Correct | 7 |
| Accuracy | 7.0% |
