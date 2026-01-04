# Mechanism-Based Capabilities Validation Scripts

## Scripts Created (Day 3 - Task 3)

1. **validate_mechanism_trial_matching.py** - Validates mechanism-based trial matching
   - 8-task verification approach
   - MVP targets: Top-3 accuracy ≥0.70, MRR ≥0.65
   - Includes MoA coverage report

2. **validate_mechanism_resistance_prediction.py** - Validates mechanism-based resistance prediction
   - 8-task verification approach
   - MVP targets: High risk AUROC ≥0.65
   - Includes baseline handling documentation

3. **validate_mbd4_tp53_mechanism_capabilities.py** - End-to-end integration test
   - Tests both trial matching AND resistance prediction together
   - MBD4+TP53 HGSOC patient scenario
   - Verifies integration success

## Status

All three scripts have been created with full implementations. See individual files for details.

## Publication-grade non-outcome validation packs

- **Sporadic gates (TumorContext) publication pack**: `scripts/validation/sporadic_gates_publication/`
  - One-command reproduce: `bash scripts/validation/sporadic_gates_publication/run_all.sh`
  - Scope: deterministic policy behavior + reproducibility (non-outcome)

## Running

```bash
# Trial matching validation
python scripts/validation/validate_mechanism_trial_matching.py

# Resistance prediction validation
python scripts/validation/validate_mechanism_resistance_prediction.py

# End-to-end integration test
python scripts/validation/validate_mbd4_tp53_mechanism_capabilities.py
```

## Reports

Each script generates a JSON report with timestamp in the same directory.
