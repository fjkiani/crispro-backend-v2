# Benchmark Modular Architecture

## Problem Statement

The benchmark scripts (`benchmark_small_test.py`, `benchmark_clinical_trial_outcomes_cbioportal.py`) were monolithic (600-700 lines each) with significant code duplication, making it:
- Hard to catch bugs (patient selection bug we just found)
- Hard to maintain (fixes needed in multiple places)
- Hard to test (no unit testing possible)
- Hard to extend (new benchmark types require copying code)

## Solution: Modular Architecture

### Module Structure

```
benchmark_common/
├── __init__.py              # Public API exports
├── data_loader.py           # Unified dataset loading
├── api_client.py            # API prediction calls
├── checkpoint.py             # Checkpoint save/load/resume
├── patient_selection.py     # Patient selection logic
└── metrics/
    ├── __init__.py
    ├── correlation.py       # PFS/OS correlation metrics
    ├── classification.py    # AUC, sensitivity, specificity
    ├── drug_ranking.py      # Drug ranking accuracy
    └── survival.py          # Kaplan-Meier, Cox regression
```

### Benefits

1. **Single Source of Truth**: Each function exists once, used everywhere
2. **Easier Testing**: Each module can be unit tested independently
3. **Easier Debugging**: Bugs fixed once, benefit all scripts
4. **Easier Extension**: New benchmark types just import modules
5. **Better Code Review**: Smaller, focused files

### Migration Status

✅ **Created**:
- `benchmark_common/__init__.py`
- `benchmark_common/data_loader.py`
- `benchmark_common/api_client.py`
- `benchmark_common/checkpoint.py`
- `benchmark_common/patient_selection.py`
- `benchmark_common/metrics/__init__.py`
- `benchmark_common/metrics/correlation.py`
- `benchmark_common/metrics/classification.py`

⏳ **In Progress**:
- `benchmark_common/metrics/drug_ranking.py`
- `benchmark_common/metrics/survival.py`

📋 **Next Steps**:
1. Complete remaining metric modules
2. Refactor `benchmark_small_test.py` to use modules
3. Refactor `benchmark_clinical_trial_outcomes_cbioportal.py` to use modules
4. Add unit tests for each module
5. Update documentation

### Usage Example

**Before (Monolithic)**:
```python
# 600 lines of duplicated code
def load_cbioportal_dataset(...):
    # 50 lines of loading logic
    ...

def predict_patient_efficacy(...):
    # 80 lines of API call logic
    ...

# ... more duplicated functions
```

**After (Modular)**:
```python
from benchmark_common import (
    load_cbioportal_dataset,
    run_benchmark,
    compute_correlation_metrics,
    save_checkpoint,
)

# Thin orchestration script (~100 lines)
patients = load_cbioportal_dataset()
predictions = await run_benchmark(patients)
metrics = compute_correlation_metrics(predictions, patients)
save_checkpoint(checkpoint_file, predictions)
```

### Key Improvements

1. **Patient Selection Bug Fixed**: Now in one place (`patient_selection.py`)
2. **Mutation Conversion Bug Fixed**: Now in one place (`api_client.py`)
3. **Checkpoint Logic Unified**: No more inconsistencies
4. **Metrics Computation Standardized**: Same logic everywhere


