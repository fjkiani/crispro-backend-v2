# Sporadic Gates (Tumor-Context) — Publication Validation Pack (Backend-Minimal)

This directory makes the **sporadic tumor-context gates** validation reproducible from the main codebase:
`oncology-coPilot/oncology-backend-minimal/`.

## What this validates (receipt-backed, non-outcome)
- **Deterministicbehavior** (PARP penalty + HRD rescue; IO boost; confidence caps) on controlled inputs.
- **Scenario-suite benchmark** that recomputes the receipt used in the manuscript: change counts + conformance vs a naive reference implementation.
- **Quick Intake coverage** (15 cancer priors) as an operational intake bridge.
- **End-to-end smoke** (Quick Intake → efficacy) producing provenance-bearing outputs.

**Not validated here:** clinical outcomes, enrollment lift, or retrospective "ground truth" trial matching.

## One-command reproduce
From `oncology-coPilot/oncology-backend-minimal/`:

```bash
# Requires the backend to be running for the E2E step (default API_BASE=http://localhost:8000)
# Example:
#   uvicorn api.main:app --reload --port 8000

bash scripts/validation/sporadic_gates_publication/run_all.sh
```

Outputs:
- Timestamped: `scripts/validation/sporadic_gates_publication/receipts/<ts>/...`
- Stable pointers: `scripts/validation/sporadic_gates_publication/receipts/latest/...`

## Files copied from theublication bundle (source receipts)
To preserve what the manuscript cited at the time, we also keep the exact publication receipts under:
- `receipts/source_publication/`

These are for comparison only; the goal is to regenerate them via `run_all.sh`.

## How to extend validation to real studies (where it already exists)
There **are** real-cohort / clinical-dataset validations in this repo, but they live outside the sporadic-gates publication pack:

- **TCGA-OV EMT/HRD analyses** (example scripts):
  - `scripts/validation/test_emt_hrd_platinum_tcga_ov.py`
  - `scripts/validation/test_emt_hrd_early_progression_tcga_ov.py`
- **Cohort summary output**:
  - `scripts/validation/real_validation_report.json` (TCGA-OV cohort size 469)

Those are outcome-linked / cohort-based checks, whereas this publication pack is intentionally scoped to **policy correctness + reproducibility**.

If you want *sporadic gates* evaluated over a real cohort, the next step is a new script that:
1) loads a cohort’s tumor biomarkers (H/TMB/MSI) per patient,
2) runs `apply_sporadic_gates()` per drug per patient,
3) summarizes how often each gate triggered + distribution of score deltas,
4) writes a receipt (JSON) and (optionally) plots.

