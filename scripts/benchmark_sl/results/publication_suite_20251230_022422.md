## Publication suite results (100-case dataset)
- **Dataset**: `test_cases_100.json`
- **API**: `http://127.0.0.1:8000`
- **Model**: `evo2_1b`
- **Fast-mode**: True (no evidence calls)

### Summary (positives + negatives)
| Method | Pos Class@1 | 95% CI | Pos Drug@1 | 95% CI | Neg PARP FP | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Random | 28.0% | [20.0%, 37.0%] | 16.0% | [9.0%, 24.0%] | 0.0% | [0.0%, 0.0%] |
| Rule (DDR→PARP) | 51.0% | [41.0%, 61.0%] | 47.0% | [37.0%, 57.0%] | 0.0% | [0.0%, 0.0%] |
| Model SP | 17.0% | [10.0%, 25.0%] | 7.0% | [2.0%, 12.0%] | 0.0% | [0.0%, 0.0%] |
| Model SPE | 17.0% | [10.0%, 25.0%] | 7.0% | [2.0%, 12.0%] | 0.0% | [0.0%, 0.0%] |

