# HRD / PARP Gate — Outcome Validation Blocker

## Summary
We can validate **the gate implementation** (unit/scenario/E2E), but we cannot make a defensible **outcome-labeled validation claim** for the “HRD rescue” component using PanCancer Atlas cBioPortal TCGA studies alone.

## Why (technical)
- The PanCan Atlas TCGA studies exposed via cBioPortal include:
  - `ANEUPLOIDY_SCORE`
  - `FRACTION_GENOME_ALTERED`
  - `TMB_NONSYNONYMOUS`
  - `MSI_SCORE_MANTIS`, `MSI_SENSOR_SCORE`
- They do **not** expose a true HRD assay / scarHRD score (e.g., LOH/LST/ntAI composite) suitable as ground truth.

## What we currently have
- A derived `hrd_proxy` based on `ANEUPLOIDY_SCORE` and `FRACTION_GENOME_ALTERED`.
- This proxy must be labeled **exploratory genome instability proxy**, not “validated H What we need to complete outcome validation
One of:
- A cohort with a measured HRD score (Myriad HRD / scarHRD / LOH+LST+ntAI)
- A trial/clinical dataset where HRD is available and PARP response endpoints exist
- A curated dataset with platinum response + HRD labels

## Recommended publication posture (honest)
- Keep the PARP gate as a **deterministic safety policy** (penalty when germline negative + HRD-low/unknown).
- Present IO validation and confidence-caps validation with receipts.
- Explicitly list HRD-rescue outcome validation as **future work** pending an HRD-labeled cohort.
