# Methods — Reproducibility Checklist

## Software Environment
- Python: 3.9.6 (macOS-14.5-arm64-arm-64bit)
- lifelines: 0.30.0
- pandas: 2.3.1
- numpy: 2.0.2
- matplotlib: 3.9.4

## Data Sources
- cBioPortal API: `https://www.cbioportal.org/api`
- TCGA-UCEC study ID: `ucec_tcga_pan_can_atlas_2018`
- TCGA-COADREAD study ID: `coadread_tcga_pan_can_atlas_2018`
- Access date: 2026-01-01

## Statistical Methods
- Kaplan–Meier estimator: `lifelines.KaplanMeierFitter`
- Log-rank test: `lifelines.statistics.logrank_test` (two-sided)
- Significance threshold: α = 0.05
- Missing data: complete-case per analysis (no imputation)

## Biomarker Definitions
- TMB: `TMB_NONSYNONYMOUS` (mutations/Mb from TCGA clinical attributes)
- TMB-high threshold: ≥ 20 mutations/Mb
- MSI: derived `msi_status` from MANTIS/MSIsensor clinical attributes
- MSI-H rule: MANTIS > 0.4 OR MSIsensor > 3.5

## Reproducibility
- Code: `biomarker_enriched_cohorts/scripts/`
- One-command: `python3 biomarker_enriched_cohorts/scripts/run_validation_suite.py`
