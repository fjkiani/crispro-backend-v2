## Publication suite results (100-case dataset)
- **Dataset**: `test_cases_100.json`
- **API**: `http://127.0.0.1:8000`
- **Model**: `evo2_1b`
- **Fast-mode**: True (no evidence calls)

### Summary (positives + negatives)
| Method | Pos Class@1 | 95% CI | Pos Drug@1 | 95% CI | Neg PARP FP | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Random | 38.6% | [27.1%, 51.4%] | 21.4% | [12.9%, 31.4%] | 33.3% | [16.7%, 50.0%] |
| Rule (DDR→PARP) | 70.0% | [60.0%, 81.4%] | 64.3% | [52.9%, 75.7%] | 33.3% | [16.7%, 50.0%] |
| Model SP | 92.9% | [85.7%, 98.6%] | 92.9% | [85.7%, 98.6%] | 0.0% | [0.0%, 0.0%] |
| Model SPE | 92.9% | [85.7%, 98.6%] | 92.9% | [85.7%, 98.6%] | 0.0% | [0.0%, 0.0%] |

