# Sporadic Gates (Tumor-Context) — Publication Validation Pack

This directory makes the **sporadic tumor-context gates** validation reproducible.

## What this validates (receipt-backed)
- **Deterministic behavior** (PARP penalty + HRD rescue; IO boost; confidence caps) on controlled inputs.
- **Scenario-suite benchmark**: 25-case suite exercising threshold boundaries.
- **Real-world impact (n=585)**: Behavioral profile across a TCGA-OV clinical cohort, quantifying trigger frequencies and overconfidence suppression.
- **Quick Intake coverage** (15 cancer priors) as an operational intake bridge.
- **End-to-end smoke** (Quick Intake → efficacy) producing provenance-bearing outputs.

## One-command reproduce
From `oncology-coPilot/oncology-backend-minimal/`:
```bash
bash scripts/validation/sporadic_gates_publication/run_all.sh
``` Key Scripts
- `scripts/compute_benchmark_gate_effects.py`: Synthetic scenario suite.
- `scripts/validate_sporadic_impact.py`: Real-world impact on TCGA-OV (n=585).
- `scripts/validate_quick_intake.py`: Coverage across 15 cancer priors.

## Receipts
- `receipts/benchmark_gate_effects.json`
- `receipts/sporadic_gates_real_world_impact.json`
- `receipts/quick_intake_15cancers.json`
