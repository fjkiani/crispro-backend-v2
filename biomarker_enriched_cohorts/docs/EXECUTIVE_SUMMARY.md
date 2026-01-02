# Sporadic Gates Validation - Executive Summary

## What We Validated ✅

**IO Boost (TMB/MSI)**:
- UCEC: TMB p=0.00105 (n=516; high=120), MSI p=0.00732 (n=527; MSI-H=174)
- COADREAD: TMB p=0.9310311851606116 (n=530; high=77), MSI p=0.7564597234812143 (n=588; MSI-H=107)
- Conclusion: IO biomarker gating is cohort-dependent; validated in UCEC with transparent null receipt in COADREAD.

**Confidence Caps (Completeness Tiering)**:
- Missingness simulation (UCEC): L2/L1/L0 = 228/214/86
- Conclusion: Tiering mechanism works under incomplete data; numeric caps remain safety policy.

## What We Did NOT Validate ❌

**HRD/PARP Outcome Validation**:
- Blocker: TCGA PanCan Atlas lacks true commercial HRD scores
- Status: Deferred (external HRD-labeled cohort needed)

## Reproducibility

- One-command: `python3 biomarker_enriched_cohorts/scripts/run_validation_suite.py`
- Receipts: SHA256 + timestamps in `biomarker_enriched_cohorts/receipts/`
- Tests: integration tests pass
